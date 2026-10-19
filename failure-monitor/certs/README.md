Extra CA certificates (`*.crt`) trusted by the monitor image, for networks with TLS inspection.
start.sh copies the file named by $REQUESTS_CA_BUNDLE or $SSL_CERT_FILE here as host-ca.crt.
