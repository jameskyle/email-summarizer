# Email Summarizer Project

## Overview
The Email Summarizer fetches and processes emails from IMAP accounts. It filters emails based on configurable criteria and generates two types of output:
- A **raw text file** with concatenated email details.
- A **Markdown formatted summary** organized into categories and with a list of recommended actions.

## Features
- **Multiple Account Support:** Configure different accounts (e.g., personal, work).
- **Filtering:** Apply sender-based filters using groups defined in the configuration.
- **Partial Processing:** Option to process only today's emails (sent after 9 AM).
- **Output Files:** Generates both a raw text dump and a structured Markdown summary.
- **Makefile Integration:** Run tasks using predefined targets in the Makefile.

## Files & Directories
```
.
├── auth.yml           # User-specific configuration (copy [example_auth.yml] and customize)
├── example_auth.yml   # Example configuration file
├── Makefile           # Build file with processing targets
├── process_emails.py  # Main Python script for processing emails
└── README.md          # This documentation file
```

## Prerequisites
- Python 3.6+
- Required Python packages:
  - `pyyaml`
  - `openai`
- Other standard libraries (`imaplib`, `email`, etc.) are part of the Python standard library.

## Installation
1. **Clone the Repository:**
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```
2. **Set up a Virtual Environment (Optional):**
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```
3. **Install Dependencies:**
   ```bash
   pip install pyyaml openai
   ```

## Configuration
- Copy the provided `example_auth.yml` file to `auth.yml` and update the configuration with your email account details:
  ```bash
  cp example_auth.yml auth.yml
  ```
- Edit `auth.yml` as needed to include your IMAP server, username, password, and any sender filters.

## Usage

### Using the Makefile
The Makefile includes targets to process and display emails. Email display in terminal requires [Glow](https://github.com/charmbracelet/glow):
- **Process Personal Emails:**
  ```bash
  make personal
  ```
- **Process Work Emails:**
  ```bash
  make work
  ```
- **Display Summaries:**
  ```bash
  make display
  ```
- **Display Partial (Today’s) Summaries:**
  ```bash
  make display-partial
  ```

### Running the Python Script Directly
Examples:
- **Process emails for a default account (e.g., work):**
  ```bash
  python process_emails.py work
  ```
- **Process emails from the past 7 days:**
  ```bash
  python process_emails.py work --days 7
  ```
- **Apply a sender filter (e.g., family):**
  ```bash
  python process_emails.py personal --filter-name priority
  ```
- **Partial processing (only today’s emails after 9 AM), requires --days 1:**
  ```bash
  python process_emails.py work --partial
  ```

## Expected Output
The script creates two types of files in the `emails/` directory:
- **Raw Text File:** Detailed email information (e.g., `2025-05-19_1_work.txt`).
- **Markdown Summary:** A structured summary file (e.g., `2025-05-19_1_work.md`).

## License
This project is licensed under the repository's license terms.

## Contributions
Contributions and suggestions are welcome. Please open an issue or submit a pull request for improvements or bug fixes.
