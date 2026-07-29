// Export bounded messages from exact Mail account (read-only).
// Usage: osascript -l JavaScript export_messages.js BF-Personal Inbox 5
function run(argv) {
  var accountName = (argv && argv[0]) || "BF-Personal";
  var mailboxName = (argv && argv[1]) || "Inbox";
  var limit = parseInt((argv && argv[2]) || "5", 10);
  if (!(limit > 0 && limit <= 50)) limit = 5;

  var Mail = Application("Mail");
  var accounts = Mail.accounts();
  var found = null;
  for (var i = 0; i < accounts.length; i++) {
    if (String(accounts[i].name()) === accountName) {
      found = accounts[i];
      break;
    }
  }
  if (!found) {
    return JSON.stringify({ ok: false, error: "account_not_found", accountName: accountName });
  }

  var mbs = found.mailboxes();
  var inbox = null;
  for (var j = 0; j < mbs.length; j++) {
    var n = String(mbs[j].name());
    if (n === mailboxName || n.toLowerCase() === mailboxName.toLowerCase()) {
      inbox = mbs[j];
      break;
    }
  }
  if (!inbox) {
    return JSON.stringify({ ok: false, error: "mailbox_not_found", mailboxName: mailboxName });
  }

  var msgs = inbox.messages();
  var count = msgs.length;
  var take = Math.min(limit, count);
  var items = [];
  for (var k = 0; k < take; k++) {
    var m = msgs[k];
    items.push({
      id: String(m.id()),
      subject: String(m.subject()),
      sender: String(m.sender()),
      dateReceived: String(m.dateReceived()),
      messageId: String(m.messageId()),
      source: String(m.source())
    });
  }
  return JSON.stringify({
    ok: true,
    accountName: accountName,
    mailbox: String(inbox.name()),
    total: count,
    exported: items.length,
    items: items
  });
}
