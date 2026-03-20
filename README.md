# url-bruteforcer
Enter your URL (e.g., helloworld.com). The bruteforcer will try paths like helloworld.com/admin.html and similar endpoints, then return response codes and data.

There are Linux tools for this, but I think a universal Python script that’s also much more customizable is way cooler.

Any errors or issues down the road will not be fixed—please troubleshoot them yourself. This package will not be updated to support future Python versions.

EXAMPLE OUTPUT
=======================================================
  SCAN SUMMARY
=======================================================
  Checked  : 385 / 385 endpoints
  200 OK   : 10
  Live     : 14  (non-404, no error)
  Errors   : 0
  Skipped  : 0
=======================================================

  [200 hits]
    https://unwater.org/cpanel
    https://unwater.org/robots.txt
    https://unwater.org/sitemap.xml
    https://unwater.org/install.php
    https://unwater.org/archive
    https://unwater.org/README.md
    https://unwater.org/user
    https://unwater.org/user/login
    https://unwater.org/user/login
    https://unwater.org/user
[+] Log saved → 'logs\responcecodes(unwater.org)(2026-03-19_17-52-15).txt'
