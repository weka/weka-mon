
# set permissions so that the continer(s) can write to these directories
mkdir -p prometheus_data
chmod 755 prometheus_data/
chown 65534 prometheus_data/
chgrp 65534 prometheus_data/

mkdir -p loki_data
chmod 755 loki_data/
chown 10001 loki_data/
chgrp 10001 loki_data/

# this is so the Grafana database persists between container restarts
chmod 755 var_lib_grafana/ etc_grafana/
chown -R 472:0 var_lib_grafana/ etc_grafana/
