#!/usr/bin/env python3
"""
Email Summarizer Script.

Connects to an IMAP server, fetches emails from a specified account within a given
timeframe, optionally filters senders by predefined groups, and generates both a
raw text dump and a structured summary via OpenAI.

Configuration (auth.yml):
    icloud:
      server: imap.mail.me.com
      username: your-user
      password: your-password
      filters:
        family:
          - mom@gmail.com
          - brother@gmail.com
    work:
      server: imap.gmail.com
      username: me@yourwork.com
      password: work-email-password

Expected Output Files:
    - Raw dump (.txt): Contains concatenated email information including Subject,
      Sender, and the complete email body. Example: "2025-05-19_1_work.txt"
    - Structured summary (.md): Contains a Markdown formatted summary which is 
      categorized into sections (e.g. Work, Career, Personal, Financial, Promotions) 
      and includes a "Recommended Actions" list.
    
Summary Formatting and Categorization:
    The summary is generated via the OpenAI API, following these rules:
      • Emails are categorized under sections such as Work, Career, Personal, Financial,
        and Promotions. Additional categories may appear if appropriate.
      • Items directly from safegraph.com or safegraph.io are marked as 'Work'.
      • Bills, credit card notices, utilities, etc. are classified under Financial.
      • A separate section (Recommended Actions) lists action items in a concise list.
      
Usage Examples:
    $ python extract_emails.py icloud
      - Fetches emails from the 'icloud' account from 1 day back and outputs:
        • emails/2025-05-19_1_icloud.txt (raw details)
        • emails/2025-05-19_1_icloud.md (formatted summary)
    $ python extract_emails.py work --days 7
      - Fetches emails from the 'work' account from the past 7 days.
    $ python extract_emails.py icloud --filter-name family
      - Applies the 'family' filter defined in auth.yml to restrict senders.
    $ python extract_emails.py work --days 3 --filter-name work
      - Fetches emails from 'work' account for the past 3 days, filtering by 'work' group.
    $ python extract_emails.py work --partial
      - Fetches only today's emails sent after 9 AM (only valid with --days 1).

For more details, refer to the script documentation.
"""
import argparse
import imaplib
import email
import yaml
import os
import sys
import re
import json
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI()

def load_config(path="auth.yml"):
    """Load email account configuration from a YAML file.

    Args:
        path (str): Path to the YAML config file. Defaults to 'auth.yml'.

    Returns:
        dict: Parsed configuration mapping account names to settings.

    Raises:
        FileNotFoundError: If the config file is not found.
        yaml.YAMLError: If the config file cannot be parsed.
    """
    with open(path) as f:
        return yaml.safe_load(f)

def get_account(cfg, name):
    """Retrieve configuration for a given account.

    Args:
        cfg (dict): Configuration dictionary.
        name (str): Account name to retrieve.

    Returns:
        dict: Configuration for the specified account.

    Raises:
        ValueError: If no account matches the given name.
    """
    acct = cfg.get(name)
    if acct is None:
        raise ValueError(f"No account named {name}")
    return acct

def connect_to_mail(server, user, pwd):
    """Establish and return an IMAP SSL connection.

    Args:
        server (str): IMAP server hostname.
        user (str): Username for login.
        pwd (str): Password for login.

    Returns:
        imaplib.IMAP4_SSL: Authenticated IMAP connection object.
    """
    m = imaplib.IMAP4_SSL(server)
    m.login(user, pwd)
    return m

def fetch_ids(mail, days):
    """Fetch email IDs from the inbox since a given number of days ago.

    Args:
        mail (imaplib.IMAP4_SSL): IMAP connection.
        days (int): Number of days to look back.

    Returns:
        list[bytes]: List of email ID bytes.
    """
    mail.select("inbox", readonly=True)
    since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    _, data = mail.search(None, f'(SINCE "{since}")')
    return data[0].split()

def filter_ids_after_time(mail, ids, after_dt):
    """Filter email IDs with 'Date' header on same day and after given time.

    Args:
        mail (imaplib.IMAP4_SSL): IMAP connection.
        ids (list[bytes]): Email ID list.
        after_dt (datetime): Datetime threshold.

    Returns:
        list[bytes]: Filtered IDs.
    """
    keep = []
    for eid in ids:
        _, fetched = mail.fetch(eid, "(BODY.PEEK[HEADER.FIELDS (DATE)])")
        raw = None
        if isinstance(fetched, list) and fetched:
            raw = fetched[0][1] if isinstance(fetched[0], tuple) else fetched[0]
        elif isinstance(fetched, (bytes, bytearray)):
            raw = fetched
        if not raw:
            continue
        hdr = email.message_from_bytes(raw)
        date_hdr = hdr.get("Date")
        if not date_hdr:
            continue
        try:
            msg_dt = parsedate_to_datetime(date_hdr)
            if msg_dt.tzinfo is None:
                msg_dt = msg_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
            msg_dt_local = msg_dt.astimezone(after_dt.tzinfo)
            if msg_dt_local.date() == after_dt.date() and msg_dt_local >= after_dt:
                keep.append(eid)
        except Exception:
            continue
    return keep

def decode_payload(part):
    """Decode an email payload to UTF-8 text.

    Args:
        part (email.message.Message): Part of an email message.

    Returns:
        str: Decoded text content, with errors replaced.
    """
    payload = part.get_payload(decode=True)
    return payload.decode("utf-8", errors="replace") if payload else ""

def extract_email_content(msg):
    """Extract plain-text content from an email message.

    Args:
        msg (email.message.Message): Parsed email message.

    Returns:
        str: The plain-text body of the message.
    """
    if msg.is_multipart():
        for p in msg.walk():
            if p.get_content_type() == "text/plain":
                return decode_payload(p)
    return decode_payload(msg)

def process_emails(ids, mail, domains_filter=None):
    """Fetch, filter, and format emails into a single text block.

    Args:
        ids (iterable[bytes]): Iterable of email ID bytes.
        mail (imaplib.IMAP4_SSL): Authenticated IMAP connection.
        domains_filter (list[str], optional): Domain suffixes to include.

    Returns:
        str: Concatenated email metadata and plain-text bodies.
    """
    out = ""
    for eid in ids:
        _, fetched = mail.fetch(eid, "(BODY[])")
        raw = None
        if isinstance(fetched, list) and fetched:
            raw = fetched[0][1] if isinstance(fetched[0], tuple) else fetched[0]
        elif isinstance(fetched, (bytes, bytearray)):
            raw = fetched
        if not raw:
            continue
        msg = email.message_from_bytes(raw)
        subj, enc = decode_header(msg.get("Subject", ""))[0]
        if isinstance(subj, bytes):
            subj = subj.decode(enc or "utf-8", errors="replace")
        frm = msg.get("From", "")
        m = re.search(r"<([^>]+)>", frm)
        addr = m.group(1) if m else frm
        if domains_filter and not any(addr.endswith(d) for d in domains_filter):
            continue
        body = extract_email_content(msg)
        out += f"Subject: {subj}\nSender: {frm}\nContent:\n{body}\n\n"
    return out

def summarize_emails(text):
    """Generate a structured summary of emails via the OpenAI API.

    Args:
        text (str): Raw concatenated email content.

    Returns:
        str: Summarized text extracted from the API response.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    instructions = f"""
#01 You are an administrative assistant whose primary task is to summarize emails
#02 You summarize emails provided in a single text from users.
#03 You never add information not in the emails
#04 You pay particular attention to items requiring action by the user such as permission slips, event deadlines, etc.
#05 You separate your summary into two sections: currently active items or items with deadlines today or in the future from today's date of {today} and items which occurred in the past or have deadlines in the past from today's date of {today}
#06 You are concise and terse, providing the summary in as few words as possible while conveying all necessary information.
#07 You respond using Markdown formatted text.
#08 You separate the summaries into category secions: Work, Career, Personal, Financial, Promotions. You may add additional categories if it makes sense.
#09 You ensure that anything coming directly from a safegraph.com or safegraph.io domain is considered a 'Work' category item.
#10 You provide a Recommended Actions section that, in an itemized list, action items that need attention.
#11 You ensure all bills, credit card payments, credit card notices, bank notices, utilities, and similar items are included in the Financial category
"""
    response = client.responses.create(
        model="gpt-4.1-mini",
        instructions=instructions,
        text={
            "format": {
                "type": "json_schema",
                "name": "summary",
                "schema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"],"additionalProperties":False},
                "strict": True,
            }
        },
        tools=[],
        store=True,
        input=[{"role":"user","content":[{"type":"input_text","text":text}]}]
    )
    return json.loads(response.output_text)["text"]

def main():
    usage_details = """
Email Summarizer Script Usage:

This script does the following:
  1. Connects via IMAP to an email account defined in the auth.yml config file.
  2. Fetches emails from the inbox based on a specified number of days back.
  3. Optionally filters emails using a predefined filter group (by sender address).
  4. Outputs two files into the 'emails' directory:
       - A raw text dump (.txt) containing the email Subject, Sender, and complete email body.
       - A Markdown summary (.md) that categorizes email content (e.g., Work, Career, Personal, Financial, Promotions)
         and includes a Recommended Actions list.
  5. For partial email processing (--partial), only emails from today after 9 AM will be considered.

Examples:
  $ python extract_emails.py icloud
      => Creates files such as: 2025-05-19_1_icloud.txt and 2025-05-19_1_icloud.md
  $ python extract_emails.py work --days 7
      => Fetch emails from the past 7 days from the 'work' account.
  $ python extract_emails.py icloud --filter-name family
      => Apply the "family" filter to restrict emails to certain senders.
  $ python extract_emails.py work --partial
      => Only process today's emails sent after 9 AM (must use with --days 1).

For more details, review the script header.
""" 
    parser = argparse.ArgumentParser(
        description=usage_details,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("account", help="Account name as defined in auth.yml")
    parser.add_argument("--days", type=int, default=1, help="Number of days back to fetch")
    parser.add_argument("--filter-name", dest="filter_name", help="Optional filter group name")
    parser.add_argument("--partial", action="store_true", default=False,
                        help="Fetch only today's emails sent after 9am")
    args = parser.parse_args()

    if args.partial and args.days != 1:
        sys.exit("--partial can only be used with --days 1")

    try:
        cfg = load_config()
        acct = get_account(cfg, args.account)
    except Exception as e:
        sys.exit(f"Config error: {e}")

    domains = None
    if args.filter_name:
        domains = acct.get("filters", {}).get(args.filter_name)
        if domains is None:
            sys.exit(f"No filter named {args.filter_name}")

    mail = connect_to_mail(acct["server"], acct["username"], acct["password"])
    try:
        ids = fetch_ids(mail, args.days)
        if args.partial:
            threshold = datetime.now().astimezone().replace(hour=9, minute=0, second=0, microsecond=0)
            ids = filter_ids_after_time(mail, ids, threshold)
        raw_summary = process_emails(ids, mail, domains_filter=domains)
    finally:
        mail.logout()

    if not raw_summary:
        raw_summary = "No emails processed.\n"

    date = datetime.now().strftime("%Y-%m-%d")
    base = f"{date}_{args.days}_{args.account}"
    if args.partial:
        base = f"{base}_partial"
    txt_path = os.path.join("emails", f"{base}.txt")
    md_path = os.path.join("emails", f"{base}.md")
    os.makedirs("emails", exist_ok=True)

    with open(txt_path, "w") as f:
        f.write(raw_summary)
    summary_text = summarize_emails(raw_summary)
    with open(md_path, "w") as f:
        f.write(summary_text)

    print(f"Wrote raw emails to {txt_path}")
    print(f"Wrote summary to {md_path}")

if __name__ == "__main__":
    main()
