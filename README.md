# Gmail Newsletter Filter Generator

This script helps you identify potential newsletters in your Gmail inbox based on unread emails and generates Gmail search queries for them. You can then easily use these queries to create filters in Gmail to manage these newsletters (e.g., apply a label, archive them, mark as read).

## Features

- Authenticates with your Gmail account using OAuth 2.0.
- Fetches unread emails based on a specified Gmail search query (defaults to `is:unread`).
- Groups emails by sender, prioritizing emails with `List-Unsubscribe` headers as likely newsletters.
- Sorts the identified senders/newsletters by:
    - The number of unread emails (most frequent first).
    - The date of the most recent email (most recent first).
- Outputs the top sorted senders along with a ready-to-use Gmail filter query (`from:(sender@example.com)`).

## Setup

1.  **Clone or Download:** Get the script files (`tidy_inbox.py`, `pyproject.toml`, `README.md`).
2.  **Enable Gmail API:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Go to "APIs & Services" -> "Library".
    *   Search for "Gmail API" and enable it.
3.  **Create OAuth 2.0 Credentials:**
    *   Go to "APIs & Services" -> "Credentials".
    *   Click "Create Credentials" -> "OAuth client ID".
    *   If prompted, configure the consent screen (select "External" user type, provide an app name, user support email, and developer contact info). You usually don't need to submit for verification for personal use scripts like this.
    *   Select "Desktop app" as the Application type.
    *   Give it a name (e.g., "Gmail Filter Script").
    *   Click "Create".
    *   Click "DOWNLOAD JSON" to download the credentials file.
    *   **IMPORTANT:** Rename the downloaded file to `credentials.json` and place it in the **same directory** as the `tidy_inbox.py` script. **Do not share this file.**
4.  **Install Dependencies using `uv`:**
    *   Make sure you have `uv` installed. If not, follow the installation instructions at [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv).
    *   Open your terminal or command prompt.
    *   Navigate to the directory containing the project files (`pyproject.toml`).
    *   Install the required dependencies:
        ```bash
        uv sync
        ```

## Usage

1.  **Run the Script:**
    *   Make sure you are in the script's directory in your terminal.
    *   Run the script using `uv run tidy-inbox`.

2.  **First Run - Authorization:**
    *   The script will open a new tab or window in your web browser asking you to log in to your Google Account and grant permission for the script to access your Gmail (read-only access).
    *   Review the permissions and click "Allow".
    *   If successful, the browser might show a "Authentication successful" message, and you can close the tab.
    *   The script will create a `token.pickle` file in the same directory to store your authorization credentials for future runs. **Do not share this file.**

3.  **Script Output:**
    *   The script will fetch emails, group them, sort them, and then print the top senders/newsletters based on your chosen criteria.
    *   For each sender, it will show:
        *   Sender's Name/Email
        *   Number of Unread Emails found from them
        *   Date of the most recent email
        *   Subject of the most recent email
        *   A `Gmail Filter Query` (e.g., `from:(newsletter@example.com)`)

4.  **Creating Filters in Gmail:**
    *   Copy the `Gmail Filter Query` provided by the script for a newsletter you want to manage.
    *   Go to your Gmail inbox in your web browser.
    *   Paste the query into the Gmail search bar at the top and press Enter.
    *   Verify that the search results show the emails you expect.
    *   Click the "Show search options" icon (looks like sliders) on the right side of the search bar.
    *   The `From` field should be pre-filled with the sender's email from your query.
    *   Click the "Create filter" button (usually at the bottom right of the search options box).
    *   Choose the actions you want Gmail to take when new emails arrive from this sender (e.g., "Skip the Inbox (Archive it)", "Apply the label: -> New label...", "Mark as read", etc.).
    *   Optionally, check "Also apply filter to matching conversations" to apply the actions to existing emails.
    *   Click "Create filter".

## Command-Line Options

You can customize the script's behavior using command-line arguments:

*   `-q` or `--query`: Specify a custom Gmail search query to find emails.
    *   Example: `uv run tidy-inbox -q "is:unread category:promotions"`
    *   Default: `is:unread`
*   `-s` or `--sort`: Choose the sorting criteria.
    *   `count`: Sort by the number of unread emails (descending).
    *   `date`: Sort by the date of the most recent email (descending).
    *   Default: `count`
*   `-n` or `--num-results`: Set the maximum number of top newsletters to display.
    *   Example: `uv run tidy-inbox -n 10`
    *   Default: `20`
*   `--max-fetch`: Set the maximum number of emails to fetch from Gmail for analysis. Increasing this might find more newsletters but takes longer and uses more API quota.
    *   Example: `uv run tidy-inbox --max-fetch 1000`
    *   Default: `500`

## Security and Privacy

-   The script requests **read-only** access to your Gmail (`gmail.readonly` scope). It cannot send emails, delete emails, or modify your account settings (other than creating the `token.json` file locally).
-   Your credentials (`credentials.json`) and authorization token (`token.pickle`) are stored locally on your computer. **Keep these files secure and do not share them.** If `token.pickle` is compromised, someone could potentially read your emails using it until it expires or is revoked. You can revoke access anytime via your [Google Account security settings](https://myaccount.google.com/permissions).

## Troubleshooting

-   **`credentials.json not found`**: Make sure you downloaded the OAuth 2.0 credentials JSON file, renamed it exactly to `credentials.json`, and placed it in the same directory as the script.
-   **Authentication Errors:** Delete `token.pickle` and run the script again to re-authenticate. Ensure the Gmail API is enabled in your Google Cloud project. Check if the credentials in `credentials.json` are for a "Desktop app".
-   **Date Parsing Errors:** The script tries to handle common date formats but might fail on unusual ones. It will print a warning and skip date comparison for affected senders.
-   **Incorrect Grouping:** Sender identification relies on the 'From' header and email address extraction. Complex 'From' headers might lead to imperfect grouping.
