
# set permissions so that the continer(s) can write to these directories
# user/group id's come from the containers themselves

# this is so the Prometheus database persists between container restarts
chmod 755 prometheus_data/
chown 65534:65534 prometheus_data/

# this is so the Loki database persists between container restarts
chmod 755 loki_data/
chown 10001:10001 loki_data/

# this is so the Grafana database persists between container restarts
chmod 755 var_lib_grafana/
chown -R 472:0 var_lib_grafana/
