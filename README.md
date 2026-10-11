# simple-job-management-dashboard

> Work in progress. The full README (setup, commands, performance notes, time spent, AI writeup) is
> written in the final phase.

## Security notes and known limitations

- **No authentication or authorization.** The brief does not ask for it, so anyone who can reach
  the app can create, update and delete jobs. Run it only on a machine or network you trust.
- **Host header checking is relaxed for local runs.** `docker-compose.yml` sets
  `DJANGO_ALLOWED_HOSTS=*` so the app works when opened by IP or hostname, for example on a remote
  VM. Django's host check protects against forged absolute URLs (password-reset emails, shared
  caches); this app has neither, so the check protects nothing here yet. `settings.py` keeps a
  strict default. To restrict it: `DJANGO_ALLOWED_HOSTS=example.com make up`.
- **`make up` publishes port 8080 on all network interfaces**, so the app is reachable from other
  machines on the same network.

### What would come next

1. Authentication (DRF authentication classes) and per-user authorization (an `owner` foreign key
   on `Job`, permission classes, list filtered by owner).
2. `DJANGO_ALLOWED_HOSTS` set to the real hostname(s), and a required `DJANGO_SECRET_KEY`.
3. TLS termination in front of nginx.
