// Apple Mail JXA export helper (read-only). Account locator is exact name match.
// Usage: osascript -l JavaScript tools/apple/mail_jxa/export_source.js BF-Personal
function run(argv) {
  var accountName = argv && argv.length ? argv[0] : "BF-Personal";
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
  return JSON.stringify({ ok: true, accountName: accountName, id: String(found.id()) });
}
