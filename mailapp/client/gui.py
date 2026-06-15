"""Tkinter desktop demo for the course mail client."""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from mailapp.auth.user_store import register_user, require_user
from mailapp.client.client_core import (
    display_email,
    list_mailbox_authenticated,
    list_recall_notifications_authenticated,
    list_recallable_sent_emails,
    receive_email_workflow,
    recall_email_workflow,
    send_email_workflow,
)
from mailapp.common.constants import FOLDER_INBOX, FOLDER_SPAM
from mailapp.common.exceptions import (
    AuthenticationError,
    MailNotFoundError,
    RecallError,
)
from mailapp.config import load_config
from mailapp.protocols.pop3_client import describe_security as describe_pop3_security
from mailapp.protocols.smtp_client import describe_security as describe_smtp_security
from mailapp.spam.classifier import model_status
from mailapp.storage.db import init_database


APP_TITLE = "MailApp Desktop Demo"


def parse_recipients(value):
    """Parse and deduplicate comma/semicolon separated recipients."""
    recipients = []
    for item in value.replace(";", ",").split(","):
        address = item.strip()
        if address and address not in recipients:
            recipients.append(address)
    return recipients


def friendly_error(exc):
    """Return a concise error suitable for GUI dialogs."""
    if isinstance(exc, AuthenticationError):
        return f"Authentication failed: {exc}"
    if isinstance(exc, RecallError):
        return f"Recall failed: {exc}"
    if isinstance(exc, MailNotFoundError):
        return f"Mail not found: {exc}"
    if isinstance(exc, ConnectionError):
        return f"Connection failed: {exc}\nPlease start run_server.py first."
    if isinstance(exc, FileNotFoundError):
        return f"File not found: {exc}"
    return f"{exc.__class__.__name__}: {exc}"


class MailDesktopApp:
    """Desktop GUI that delegates all mail operations to client_core."""

    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x760")
        self.root.minsize(960, 640)

        self.username = tk.StringVar(value="alice@example.com")
        self.password = tk.StringVar(value="alice123")
        self.session_user = None
        self.status = tk.StringVar(value="Ready. Start run_server.py before network operations.")
        self.attachments = []
        self.busy_widgets = []

        self._configure_style()
        self._build_header()
        self._build_notebook()
        self._build_status_bar()
        self._set_authenticated(False)
        self.refresh_system_status()

    def _configure_style(self):
        style = ttk.Style()
        available = style.theme_names()
        if "clam" in available:
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("Heading.TLabel", font=("TkDefaultFont", 11, "bold"))
        style.configure("Primary.TButton", font=("TkDefaultFont", 10, "bold"))
        style.configure("Treeview", rowheight=28)

    def _build_header(self):
        frame = ttk.Frame(self.root, padding=(16, 12))
        frame.pack(fill="x")
        ttk.Label(frame, text="MailApp Desktop Demo", style="Title.TLabel").grid(
            row=0, column=0, columnspan=6, sticky="w", pady=(0, 8)
        )
        ttk.Label(frame, text="Username").grid(row=1, column=0, sticky="w")
        self.username_entry = ttk.Entry(frame, textvariable=self.username, width=30)
        self.username_entry.grid(row=1, column=1, padx=(6, 16), sticky="ew")
        ttk.Label(frame, text="Password").grid(row=1, column=2, sticky="w")
        self.password_entry = ttk.Entry(
            frame, textvariable=self.password, width=22, show="*"
        )
        self.password_entry.grid(row=1, column=3, padx=(6, 16), sticky="ew")
        self.login_button = ttk.Button(
            frame, text="Login", command=self.login, style="Primary.TButton"
        )
        self.login_button.grid(row=1, column=4, padx=(0, 8))
        self.register_button = ttk.Button(
            frame, text="Register", command=self.show_register_dialog
        )
        self.register_button.grid(row=1, column=5, padx=(0, 8))
        self.logout_button = ttk.Button(frame, text="Logout", command=self.logout)
        self.logout_button.grid(row=1, column=6)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

    def _build_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.compose_tab = ttk.Frame(self.notebook, padding=14)
        self.inbox_tab = ttk.Frame(self.notebook, padding=14)
        self.spam_tab = ttk.Frame(self.notebook, padding=14)
        self.sent_tab = ttk.Frame(self.notebook, padding=14)
        self.notifications_tab = ttk.Frame(self.notebook, padding=14)
        self.system_tab = ttk.Frame(self.notebook, padding=14)
        for frame, label in (
            (self.compose_tab, "Compose"),
            (self.inbox_tab, "Inbox"),
            (self.spam_tab, "Spam"),
            (self.sent_tab, "Sent / Recall"),
            (self.notifications_tab, "Recall Notifications"),
            (self.system_tab, "TLS & Model"),
        ):
            self.notebook.add(frame, text=label)
        self._build_compose_tab()
        self.inbox_tree = self._build_mailbox_tab(
            self.inbox_tab, FOLDER_INBOX, include_receive=True
        )
        self.spam_tree = self._build_mailbox_tab(
            self.spam_tab, FOLDER_SPAM, include_receive=False
        )
        self._build_sent_tab()
        self._build_notifications_tab()
        self._build_system_tab()

    def _build_compose_tab(self):
        tab = self.compose_tab
        ttk.Label(tab, text="Recipients").grid(row=0, column=0, sticky="nw", pady=5)
        self.recipient_entry = ttk.Entry(tab)
        self.recipient_entry.grid(row=0, column=1, columnspan=4, sticky="ew", pady=5)
        ttk.Label(tab, text="Subject").grid(row=1, column=0, sticky="nw", pady=5)
        self.subject_entry = ttk.Entry(tab)
        self.subject_entry.grid(row=1, column=1, columnspan=4, sticky="ew", pady=5)
        ttk.Label(tab, text="Body").grid(row=2, column=0, sticky="nw", pady=5)
        self.body_text = tk.Text(tab, height=19, wrap="word", undo=True)
        self.body_text.grid(row=2, column=1, columnspan=4, sticky="nsew", pady=5)

        self.html_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(tab, text="Send as HTML", variable=self.html_var).grid(
            row=3, column=1, sticky="w", pady=5
        )
        self.attachment_label = ttk.Label(tab, text="No attachments")
        self.attachment_label.grid(row=3, column=2, sticky="w", pady=5)
        attach_button = ttk.Button(tab, text="Add Attachments", command=self.choose_attachments)
        attach_button.grid(row=3, column=3, padx=5)
        clear_attach_button = ttk.Button(
            tab, text="Clear Attachments", command=self.clear_attachments
        )
        clear_attach_button.grid(row=3, column=4)

        button_row = ttk.Frame(tab)
        button_row.grid(row=4, column=1, columnspan=4, sticky="ew", pady=(12, 0))
        normal_button = ttk.Button(
            button_row, text="Fill Normal Demo", command=self.fill_normal_demo
        )
        normal_button.pack(side="left")
        spam_button = ttk.Button(
            button_row, text="Fill Spam Demo", command=self.fill_spam_demo
        )
        spam_button.pack(side="left", padx=8)
        clear_button = ttk.Button(button_row, text="Clear", command=self.clear_compose)
        clear_button.pack(side="left")
        send_button = ttk.Button(
            button_row, text="Send Email", command=self.send_email,
            style="Primary.TButton"
        )
        send_button.pack(side="right")
        self.busy_widgets.extend(
            [attach_button, clear_attach_button, normal_button, spam_button, send_button]
        )
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(2, weight=1)
        tab.rowconfigure(2, weight=1)

    def _build_mailbox_tab(self, tab, folder, include_receive):
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 10))
        if include_receive:
            receive_button = ttk.Button(
                toolbar,
                text="Receive via POP3",
                command=self.receive_messages,
                style="Primary.TButton",
            )
            receive_button.pack(side="left")
            self.busy_widgets.append(receive_button)
        refresh_button = ttk.Button(
            toolbar,
            text="Refresh",
            command=lambda: self.refresh_mailbox(folder),
        )
        refresh_button.pack(side="left", padx=8)
        open_button = ttk.Button(
            toolbar,
            text="Open Selected",
            command=lambda: self.open_selected_mail(folder),
        )
        open_button.pack(side="left")
        self.busy_widgets.extend([refresh_button, open_button])

        columns = ("subject", "sender", "status", "time", "mail_id")
        tree = ttk.Treeview(tab, columns=columns, show="headings", selectmode="browse")
        headings = {
            "subject": ("Subject", 280),
            "sender": ("Sender", 190),
            "status": ("Status", 90),
            "time": ("Time", 155),
            "mail_id": ("Server mail_id", 300),
        }
        for name, (label, width) in headings.items():
            tree.heading(name, text=label)
            tree.column(name, width=width, minwidth=70)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        tree.bind("<Double-1>", lambda _event: self.open_selected_mail(folder))
        return tree

    def _build_sent_tab(self):
        toolbar = ttk.Frame(self.sent_tab)
        toolbar.pack(fill="x", pady=(0, 10))
        refresh_button = ttk.Button(
            toolbar, text="Refresh Sent", command=self.refresh_sent
        )
        refresh_button.pack(side="left")
        recall_button = ttk.Button(
            toolbar,
            text="Recall Selected",
            command=self.recall_selected,
            style="Primary.TButton",
        )
        recall_button.pack(side="left", padx=8)
        self.busy_widgets.extend([refresh_button, recall_button])

        columns = ("subject", "status", "time", "mail_id")
        self.sent_tree = ttk.Treeview(
            self.sent_tab, columns=columns, show="headings", selectmode="browse"
        )
        for name, label, width in (
            ("subject", "Subject", 340),
            ("status", "Status", 100),
            ("time", "Time", 170),
            ("mail_id", "Server mail_id", 360),
        ):
            self.sent_tree.heading(name, text=label)
            self.sent_tree.column(name, width=width, minwidth=80)
        self.sent_tree.pack(fill="both", expand=True)

    def _build_notifications_tab(self):
        toolbar = ttk.Frame(self.notifications_tab)
        toolbar.pack(fill="x", pady=(0, 10))
        refresh_button = ttk.Button(
            toolbar, text="Refresh Notifications", command=self.refresh_notifications
        )
        refresh_button.pack(side="left")
        self.busy_widgets.append(refresh_button)
        columns = ("time", "mail_id", "message")
        self.notification_tree = ttk.Treeview(
            self.notifications_tab, columns=columns, show="headings"
        )
        for name, label, width in (
            ("time", "Time", 180),
            ("mail_id", "Mail ID", 320),
            ("message", "Notification", 560),
        ):
            self.notification_tree.heading(name, text=label)
            self.notification_tree.column(name, width=width, minwidth=90)
        self.notification_tree.pack(fill="both", expand=True)

    def _build_system_tab(self):
        toolbar = ttk.Frame(self.system_tab)
        toolbar.pack(fill="x", pady=(0, 12))
        ttk.Button(
            toolbar, text="Refresh Status", command=self.refresh_system_status
        ).pack(side="left")
        self.system_text = tk.Text(
            self.system_tab, wrap="word", state="disabled", font=("TkFixedFont", 11)
        )
        self.system_text.pack(fill="both", expand=True)

    def _build_status_bar(self):
        frame = ttk.Frame(self.root, padding=(12, 6))
        frame.pack(fill="x")
        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=150)
        self.progress.pack(side="right")
        ttk.Label(frame, textvariable=self.status).pack(side="left", fill="x", expand=True)

    def _set_authenticated(self, authenticated):
        state = "normal" if authenticated else "disabled"
        for index in range(self.notebook.index("end")):
            self.notebook.tab(index, state=state)
        if not authenticated:
            self.notebook.tab(self.system_tab, state="normal")
            self.notebook.select(self.system_tab)
        self.username_entry.configure(state="disabled" if authenticated else "normal")
        self.password_entry.configure(state="disabled" if authenticated else "normal")
        self.login_button.configure(state="disabled" if authenticated else "normal")
        self.register_button.configure(state="disabled" if authenticated else "normal")
        self.logout_button.configure(state="normal" if authenticated else "disabled")

    def _credentials(self):
        return self.username.get().strip(), self.password.get()

    def _run_task(self, label, task, on_success=None):
        self.status.set(label)
        self.progress.start(10)
        for widget in self.busy_widgets:
            widget.configure(state="disabled")

        def worker():
            try:
                result = task()
            except Exception as exc:
                self.root.after(0, lambda: self._task_failed(exc))
                return
            self.root.after(0, lambda: self._task_succeeded(result, on_success))

        threading.Thread(target=worker, daemon=True).start()

    def _task_failed(self, exc):
        self._finish_task()
        self.status.set("Operation failed")
        messagebox.showerror("MailApp", friendly_error(exc), parent=self.root)

    def _task_succeeded(self, result, callback):
        self._finish_task()
        if callback:
            callback(result)

    def _finish_task(self):
        self.progress.stop()
        for widget in self.busy_widgets:
            widget.configure(state="normal")

    def login(self):
        username, password = self._credentials()
        if not username or not password:
            messagebox.showwarning("Login", "Enter username and password.", parent=self.root)
            return

        def success(_result):
            self.session_user = username
            self._set_authenticated(True)
            self.status.set(f"Logged in as {username}")
            self.refresh_mailbox(FOLDER_INBOX)
            self.refresh_sent()
            self.refresh_notifications()

        self._run_task("Checking credentials...", lambda: require_user(username, password), success)

    def show_register_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Register New Account")
        dialog.geometry("430x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        email = tk.StringVar()
        password = tk.StringVar()
        confirmation = tk.StringVar()

        ttk.Label(frame, text="Email address").grid(row=0, column=0, sticky="w", pady=7)
        email_entry = ttk.Entry(frame, textvariable=email, width=32)
        email_entry.grid(row=0, column=1, sticky="ew", pady=7)
        ttk.Label(frame, text="Password").grid(row=1, column=0, sticky="w", pady=7)
        ttk.Entry(frame, textvariable=password, show="*", width=32).grid(
            row=1, column=1, sticky="ew", pady=7
        )
        ttk.Label(frame, text="Confirm password").grid(
            row=2, column=0, sticky="w", pady=7
        )
        ttk.Entry(frame, textvariable=confirmation, show="*", width=32).grid(
            row=2, column=1, sticky="ew", pady=7
        )
        ttk.Label(
            frame,
            text="Use an email-format username and at least 6 password characters.",
            wraplength=370,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 12))

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e")

        def submit():
            username = email.get().strip().lower()
            secret = password.get()
            if secret != confirmation.get():
                messagebox.showwarning(
                    "Register", "The two passwords do not match.", parent=dialog
                )
                return
            try:
                register_user(username, secret)
            except Exception as exc:
                messagebox.showerror("Register", friendly_error(exc), parent=dialog)
                return
            self.username.set(username)
            self.password.set(secret)
            dialog.destroy()
            messagebox.showinfo(
                "Register",
                f"Account {username} was created. Click Login to continue.",
                parent=self.root,
            )

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(
            side="left", padx=8
        )
        ttk.Button(
            buttons, text="Create Account", command=submit, style="Primary.TButton"
        ).pack(side="left")
        frame.columnconfigure(1, weight=1)
        email_entry.focus_set()
        dialog.bind("<Return>", lambda _event: submit())

    def logout(self):
        self.session_user = None
        self._set_authenticated(False)
        self.status.set("Logged out")

    def choose_attachments(self):
        paths = filedialog.askopenfilenames(title="Choose attachments", parent=self.root)
        if paths:
            self.attachments = list(paths)
            self.attachment_label.configure(
                text=f"{len(self.attachments)} attachment(s): "
                + ", ".join(Path(path).name for path in self.attachments)
            )

    def clear_attachments(self):
        self.attachments = []
        self.attachment_label.configure(text="No attachments")

    def fill_normal_demo(self):
        self.recipient_entry.delete(0, "end")
        self.recipient_entry.insert(0, "bob@example.com")
        self.subject_entry.delete(0, "end")
        self.subject_entry.insert(0, "Computer Network Project Demo")
        self.body_text.delete("1.0", "end")
        self.body_text.insert(
            "1.0",
            "Hello Bob,\n\nPlease review the attached computer network project report.\n\nAlice",
        )
        self.html_var.set(False)

    def fill_spam_demo(self):
        self.recipient_entry.delete(0, "end")
        self.recipient_entry.insert(0, "bob@example.com")
        self.subject_entry.delete(0, "end")
        self.subject_entry.insert(0, "Win Lottery Now")
        self.body_text.delete("1.0", "end")
        self.body_text.insert(
            "1.0",
            "Congratulations! Claim your free cash prize and lottery money now. Click this urgent offer.",
        )
        self.html_var.set(False)

    def clear_compose(self):
        self.recipient_entry.delete(0, "end")
        self.subject_entry.delete(0, "end")
        self.body_text.delete("1.0", "end")
        self.html_var.set(False)
        self.clear_attachments()

    def send_email(self):
        username, password = self._credentials()
        recipients = parse_recipients(self.recipient_entry.get())
        subject = self.subject_entry.get().strip()
        body = self.body_text.get("1.0", "end-1c")
        attachments = list(self.attachments)
        if not recipients:
            messagebox.showwarning("Compose", "Enter at least one recipient.", parent=self.root)
            return
        if not subject:
            messagebox.showwarning("Compose", "Enter a subject.", parent=self.root)
            return

        def success(receipt):
            self.status.set("Email sent successfully")
            messagebox.showinfo(
                "Sent",
                "Email sent successfully.\n\n"
                f"Message-ID: {receipt['message_id']}\n"
                f"Server mail_id: {receipt['server_mail_id'] or 'pending'}",
                parent=self.root,
            )
            self.refresh_sent()

        self._run_task(
            "Sending through SMTP STARTTLS...",
            lambda: send_email_workflow(
                username,
                password,
                recipients,
                subject,
                body,
                attachments=attachments,
                html=self.html_var.get(),
            ),
            success,
        )

    def receive_messages(self):
        username, password = self._credentials()

        def success(rows):
            spam_count = sum(1 for row in rows if row["is_spam"])
            self.status.set(
                f"POP3 received {len(rows)} message(s); {spam_count} classified as spam"
            )
            self.refresh_mailbox(FOLDER_INBOX)
            self.refresh_mailbox(FOLDER_SPAM)
            messagebox.showinfo(
                "Receive Complete",
                f"Received {len(rows)} message(s).\n"
                f"Spam detected: {spam_count}\n"
                "Raw .eml files and attachments were saved locally.",
                parent=self.root,
            )

        self._run_task(
            "Receiving through POP3 STLS and running spam model...",
            lambda: receive_email_workflow(username, password, save_local=True),
            success,
        )

    def refresh_mailbox(self, folder):
        if not self.session_user:
            return
        username, password = self._credentials()
        tree = self.inbox_tree if folder == FOLDER_INBOX else self.spam_tree

        def success(rows):
            self._replace_tree(
                tree,
                [
                    (
                        row["subject"],
                        row["sender"],
                        row["status"],
                        row["created_at"],
                        row["mail_id"],
                    )
                    for row in rows
                ],
            )
            self.status.set(f"{folder.title()}: {len(rows)} message(s)")

        self._run_task(
            f"Loading {folder}...",
            lambda: list_mailbox_authenticated(username, password, folder),
            success,
        )

    def open_selected_mail(self, folder):
        tree = self.inbox_tree if folder == FOLDER_INBOX else self.spam_tree
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Open Email", "Select an email first.", parent=self.root)
            return
        mail_id = tree.item(selection[0], "values")[4]
        username, password = self._credentials()
        self._run_task(
            "Opening email...",
            lambda: display_email(mail_id, username, password),
            self._show_message_window,
        )

    def _show_message_window(self, data):
        window = tk.Toplevel(self.root)
        window.title(f"Email - {data.get('mail_id', '')}")
        window.geometry("820x620")
        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        headers = data.get("headers") or {}
        details = (
            f"Status: {data.get('status', '')}\n"
            f"From: {headers.get('sender', '')}\n"
            f"To: {', '.join(headers.get('recipients', []))}\n"
            f"Subject: {headers.get('subject', '')}\n"
            f"Date: {headers.get('date', '')}\n"
            f"Server mail_id: {data.get('mail_id', '')}\n"
            f"Body type: {data.get('body_type', '')}"
        )
        ttk.Label(frame, text=details, justify="left").pack(fill="x", pady=(0, 10))
        body = tk.Text(frame, wrap="word")
        body.insert("1.0", data.get("body", ""))
        body.configure(state="disabled")
        body.pack(fill="both", expand=True)
        ttk.Button(frame, text="Close", command=window.destroy).pack(
            anchor="e", pady=(10, 0)
        )

    def refresh_sent(self):
        if not self.session_user:
            return
        username, password = self._credentials()

        def success(rows):
            self._replace_tree(
                self.sent_tree,
                [
                    (row["subject"], row["status"], row["created_at"], row["mail_id"])
                    for row in rows
                ],
            )
            self.status.set(f"Recallable sent mail: {len(rows)}")

        self._run_task(
            "Loading sent mail...",
            lambda: list_recallable_sent_emails(username, password),
            success,
        )

    def recall_selected(self):
        selection = self.sent_tree.selection()
        if not selection:
            messagebox.showwarning("Recall", "Select a sent email first.", parent=self.root)
            return
        values = self.sent_tree.item(selection[0], "values")
        subject, mail_id = values[0], values[3]
        if not messagebox.askyesno(
            "Confirm Recall",
            f"Recall this email from all project recipients?\n\n{subject}\n{mail_id}",
            parent=self.root,
        ):
            return
        username, password = self._credentials()

        def success(result):
            self.status.set(f"Recalled {result['mail_id']}")
            messagebox.showinfo("Recall Complete", result["message"], parent=self.root)
            self.refresh_sent()

        self._run_task(
            "Recalling email...",
            lambda: recall_email_workflow(username, password, mail_id),
            success,
        )

    def refresh_notifications(self):
        if not self.session_user:
            return
        username, password = self._credentials()

        def success(rows):
            self._replace_tree(
                self.notification_tree,
                [
                    (row["created_at"], row["mail_id"], row["message"])
                    for row in rows
                ],
            )
            self.status.set(f"Recall notifications: {len(rows)}")

        self._run_task(
            "Loading recall notifications...",
            lambda: list_recall_notifications_authenticated(username, password),
            success,
        )

    def refresh_system_status(self):
        smtp = describe_smtp_security()
        pop3 = describe_pop3_security()
        model = model_status()
        text = (
            "Transport Security\n"
            "==================\n"
            f"SMTP: {smtp['host']}:{smtp['port']}\n"
            f"  mode: {smtp['security']}\n"
            f"  verify certificate: {smtp['verify_certificate']}\n"
            f"  CA file: {smtp['cafile'] or '(system trust store)'}\n\n"
            f"POP3: {pop3['host']}:{pop3['port']}\n"
            f"  mode: {pop3['security']}\n"
            f"  verify certificate: {pop3['verify_certificate']}\n"
            f"  CA file: {pop3['cafile'] or '(system trust store)'}\n\n"
            "Spam Classifier\n"
            "===============\n"
            f"Available: {model['available']}\n"
            f"Model: {model['mode']}\n"
            f"Training samples: {model.get('training_samples', '-')}\n"
            f"Path: {model['path']}\n\n"
            "Demo Accounts\n"
            "=============\n"
            "alice@example.com / alice123\n"
            "bob@example.com / bob123\n"
        )
        self.system_text.configure(state="normal")
        self.system_text.delete("1.0", "end")
        self.system_text.insert("1.0", text)
        self.system_text.configure(state="disabled")

    @staticmethod
    def _replace_tree(tree, rows):
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=row)


def run_gui():
    """Initialize project storage and start the Tkinter event loop."""
    load_config()
    init_database()
    root = tk.Tk()
    MailDesktopApp(root)
    root.mainloop()
