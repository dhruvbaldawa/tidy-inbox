import os
import pickle
import argparse
import urllib.parse
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from email.utils import parseaddr
from email.header import decode_header
import base64
from datetime import datetime, timezone
from collections import defaultdict
import re
import time
from dateutil import parser as date_parser

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

console = Console()


def decode_email_header(header):
    # Decodes email headers to handle different character sets
    decoded_header = decode_header(header)
    decoded_parts = []
    for part in decoded_header:
        if part[1] is not None:
            decoded_parts.append(part[0].decode(part[1]))
        else:
            decoded_parts.append(part[0])
    return ' '.join(decoded_parts)


def authenticate_gmail():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                console.print(f"[bold red]Error refreshing token: {e}[/bold red]")
                console.print("Attempting re-authentication...")
                creds = None # Force re-authentication
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle') # Remove potentially invalid token
        if not creds: # Proceed with flow if refresh failed or no token exists
            if not os.path.exists('credentials.json'):
                console.print("[bold red]Error:[/bold red] 'credentials.json' not found. Please download it from Google Cloud Console.")
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                console.print(f"[bold red]Error during authentication flow: {e}[/bold red]")
                return None
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            console.print("[green]Authentication successful. Token saved.[/green]")
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        console.print(f"[bold red]Error building Gmail service: {e}[/bold red]")
        return None


def fetch_unread_emails(service, query='is:unread', max_results=500):
    all_messages = []
    page_token = None
    fetched_count = 0

    console.print(f"Fetching emails with query: [cyan]'{query}'[/cyan] (max: {max_results})...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True
    ) as progress:
        fetch_task = progress.add_task("Fetching message list", total=None) # Indeterminate initially

        while fetched_count < max_results:
            try:
                results = service.users().messages().list(
                    userId='me', q=query, pageToken=page_token, maxResults=min(100, max_results - fetched_count)
                ).execute()
                messages = results.get('messages', [])
                if not messages:
                    progress.update(fetch_task, completed=fetched_count, total=fetched_count, description="No more messages found.")
                    break

                all_messages.extend(messages)
                fetched_count += len(messages)
                progress.update(fetch_task, total=results.get('resultSizeEstimate', fetched_count), completed=fetched_count, description=f"Fetched {fetched_count} message IDs")

                page_token = results.get('nextPageToken')
                if not page_token:
                    progress.update(fetch_task, completed=fetched_count, total=fetched_count, description=f"Finished fetching {fetched_count} message IDs")
                    break

                # Optional: Add a small delay to avoid hitting rate limits aggressively
                # time.sleep(0.1)

            except Exception as e:
                console.print(f"\n[bold red]Error fetching message list: {e}[/bold red]")
                progress.stop()
                return None

    if not all_messages:
        console.print("[yellow]No messages found matching the query.[/yellow]")
        return []

    detailed_messages = []
    console.print(f"Found {len(all_messages)} messages. Fetching details...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        "({task.completed}/{task.total})",
        console=console,
        transient=True
    ) as progress:
        detail_task = progress.add_task("Fetching message details", total=len(all_messages))

        for i, message_info in enumerate(all_messages):
            msg_id = message_info['id']
            try:
                # Fetch only necessary headers and minimal payload info
                msg = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From', 'Subject', 'Date', 'List-Unsubscribe']).execute()
                detailed_messages.append(msg)
                progress.update(detail_task, advance=1)
                # Optional: Add a small delay
                # time.sleep(0.05)
            except Exception as e:
                console.print(f"\n[bold red]Error fetching details for message ID {msg_id}: {e}[/bold red]")
                # Decide whether to continue or stop. Here, we continue.
                progress.update(detail_task, advance=1) # Still advance to not stall progress bar

    console.print(f"Finished fetching details for {len(detailed_messages)} messages.")
    return detailed_messages


def group_emails(messages):
    groups = defaultdict(lambda: {'count': 0, 'ids': [], 'latest_date': None, 'subject': None, 'sender_display': None, 'has_list_unsubscribe': False})
    sender_email_pattern = re.compile(r'<(.*?)>') # To extract email from "Name <email>"

    console.print("Grouping emails...")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), console=console, transient=True) as progress:
        group_task = progress.add_task("Processing messages", total=len(messages))

        for msg in messages:
            headers = msg.get('payload', {}).get('headers', [])
            sender = 'Unknown Sender'
            sender_email = None
            subject = 'No Subject'
            date_str = None
            msg_has_list_unsubscribe = False

            for header in headers:
                name = header.get('name').lower()
                value = header.get('value')
                if name == 'from':
                    sender = decode_email_header(value)
                    addr = parseaddr(sender)
                    if addr[1]: # Use the email part if available
                        sender_email = addr[1]
                    else: # Fallback if parseaddr fails
                        match = sender_email_pattern.search(sender)
                        sender_email = match.group(1) if match else sender # Use full sender if pattern fails
                elif name == 'subject':
                    subject = decode_email_header(value)
                elif name == 'date':
                    date_str = value
                elif name == 'list-unsubscribe':
                    msg_has_list_unsubscribe = True

            if not sender_email:
                console.print(f"[yellow]Warning: Could not extract email address from sender: {sender}[/yellow]")
                progress.update(group_task, advance=1)
                continue # Skip emails where we couldn't find a sender email

            current_group = groups[sender_email]
            current_group['count'] += 1
            current_group['ids'].append(msg.get('id'))
            current_group['has_list_unsubscribe'] = current_group['has_list_unsubscribe'] or msg_has_list_unsubscribe

            # Parse date and update latest
            if date_str:
                try:
                    # Use dateutil.parser for robust date parsing
                    msg_date = date_parser.parse(date_str).astimezone(timezone.utc)
                    if current_group['latest_date'] is None or msg_date > current_group['latest_date']:
                        current_group['latest_date'] = msg_date
                        current_group['subject'] = subject # Keep subject of the latest email
                        current_group['sender_display'] = sender # Keep display name from latest email
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not parse date '{date_str}' for sender {sender_email}: {e}[/yellow]")

            progress.update(group_task, advance=1)

    console.print(f"Finished grouping. Identified {len(groups)} potential senders.")

    # Filter groups: Keep only those with List-Unsubscribe OR more than 1 email
    filtered_groups = {
        sender: data for sender, data in groups.items()
        if data['has_list_unsubscribe'] or data['count'] > 1
    }
    console.print(f"Filtered down to {len(filtered_groups)} potential newsletters (having List-Unsubscribe or >1 email).")
    return filtered_groups


def sort_groups(groups, criteria='count'):
    console.print(f"Sorting groups by {criteria}...")
    if criteria == 'count':
        # Sort by count descending, then latest date descending as tie-breaker
        sorted_items = sorted(groups.items(), key=lambda item: (item[1]['count'], item[1]['latest_date'] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    elif criteria == 'date':
        # Sort by latest date descending, then count descending as tie-breaker
        sorted_items = sorted(groups.items(), key=lambda item: (item[1]['latest_date'] or datetime.min.replace(tzinfo=timezone.utc), item[1]['count']), reverse=True)
    else:
        console.print(f"[yellow]Warning:[/yellow] Invalid sort criteria '{criteria}'. Defaulting to count.")
        sorted_items = sorted(groups.items(), key=lambda item: (item[1]['count'], item[1]['latest_date'] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    console.print("Sorting complete.")
    return sorted_items


def generate_filter_query(sender_email):
    # Basic query focusing on the sender's email address
    return f"from:({sender_email})"


def main():
    parser = argparse.ArgumentParser(description='Generate Gmail filter queries for newsletters.')
    parser.add_argument('-q', '--query', default='is:unread', help='Gmail search query to find emails (default: "is:unread")')
    parser.add_argument('-s', '--sort', choices=['count', 'date'], default='count', help='Sort criteria: "count" (unread count) or "date" (most recent)')
    parser.add_argument('-n', '--num-results', type=int, default=20, help='Number of top newsletters to display (default: 20)')
    parser.add_argument('--max-fetch', type=int, default=500, help='Maximum number of emails to fetch for analysis (default: 500)')

    args = parser.parse_args()

    console.print(Panel("[bold green]Starting Tidy Inbox...[/bold green]"))
    service = authenticate_gmail()
    if not service:
        console.print("[bold red]Exiting due to authentication failure.[/bold red]")
        return

    messages = fetch_unread_emails(service, query=args.query, max_results=args.max_fetch)
    if not messages:
        # Message already printed in fetch_unread_emails if empty
        console.print("[yellow]No emails to process further. Exiting.[/yellow]")
        return

    newsletter_groups = group_emails(messages)
    if not newsletter_groups:
        console.print("[yellow]No potential newsletters identified based on filtering criteria. Exiting.[/yellow]")
        return

    sorted_newsletters = sort_groups(newsletter_groups, criteria=args.sort)

    console.print(f"\n[bold]--- Top Newsletters ---[/bold]")
    console.print(f"Sorted by: [bold cyan]{args.sort.capitalize()}[/bold cyan]")
    console.print(f"Displaying top {min(args.num_results, len(sorted_newsletters))} results:\n")

    for i, (sender_email, data) in enumerate(sorted_newsletters[:args.num_results]):
        filter_query = generate_filter_query(sender_email)
        full_filter_string = f"{args.query} {filter_query}"
        encoded_query = urllib.parse.quote_plus(full_filter_string)
        search_url = f"https://mail.google.com/mail/u/0/#search/{encoded_query}"
        date_str = data['latest_date'].strftime('%Y-%m-%d %H:%M %Z') if data['latest_date'] else 'N/A'

        # Build content for the panel using Text.assemble for cleaner formatting
        content = Text.assemble(
            ("Sender:", "bold white"), f" {data.get('sender_display', sender_email)}\n",
            ("Filter Query:", "bold white"), (f" {full_filter_string}", "bold cyan"), "\n",
            ("Search Link:", "bold white"), (f" {search_url}", "link " + search_url), "\n",
            ("Count:", "bold white"), (f" {data['count']}", "bold magenta"), (" | ", "dim"),
            ("Recent:", "dim"), (f" {date_str}", "green" if args.sort == 'date' else "dim green"), (" | ", "dim"),
            ("Subject:", "dim"), (f" {data.get('subject', 'N/A')}", "italic dim"),
        )

        panel = Panel(
            content,
            title=f"[white]{i+1}.[/white] [bold blue]{sender_email}[/bold blue]",
            border_style="blue",
            padding=(1, 2), # Add vertical padding
            expand=False
        )
        console.print(panel)

if __name__ == '__main__':
    main()
