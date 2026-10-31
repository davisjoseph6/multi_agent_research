"""Single-process, threaded WSGI setup for the SQLite-backed RCT candidate.

Use only behind one TLS-terminating Nginx reverse proxy on the same machine.
No public listener and no multi-process write contention.
"""
import os

bind = "127.0.0.1:8077"
workers = 1
worker_class = "gthread"
threads = 8
timeout = 120
graceful_timeout = 30
keepalive = 5
umask = 0o077
accesslog = None  # Do not accidentally log invitation codes or participant metadata.
errorlog = "-"
capture_output = False
forwarded_allow_ips = "127.0.0.1"
proc_name = "ijcai-rct-candidate"
