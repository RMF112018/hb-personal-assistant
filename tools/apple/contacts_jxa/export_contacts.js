// Export bounded contacts (read-only). Usage: osascript -l JavaScript export_contacts.js 20
function run(argv) {
  var limit = parseInt((argv && argv[0]) || "20", 10);
  if (!(limit > 0 && limit <= 100)) limit = 20;
  var app = Application("Contacts");
  var people = app.people();
  var total = people.length;
  var take = Math.min(limit, total);
  var items = [];
  for (var i = 0; i < take; i++) {
    var p = people[i];
    var emails = [];
    try {
      var em = p.emails();
      for (var j = 0; j < Math.min(em.length, 10); j++) {
        emails.push({ label: String(em[j].label() || ""), value: String(em[j].value() || "") });
      }
    } catch (e1) {}
    var phones = [];
    try {
      var ph = p.phones();
      for (var k = 0; k < Math.min(ph.length, 10); k++) {
        phones.push({ label: String(ph[k].label() || ""), value: String(ph[k].value() || "") });
      }
    } catch (e2) {}
    var contactType = "person";
    var org = String(p.organization() || "");
    if (org === "null") org = "";
    var fn = String(p.firstName() || "");
    var ln = String(p.lastName() || "");
    if (fn === "null") fn = "";
    if (ln === "null") ln = "";
    if (!fn && !ln && org) contactType = "organization";
    items.push({
      cn_id: String(p.id()),
      first_name: fn,
      last_name: ln,
      organization: org,
      contact_type: contactType,
      container: "On My Mac",
      emails: emails,
      phones: phones
    });
  }
  return JSON.stringify({ ok: true, total: total, exported: items.length, items: items });
}
