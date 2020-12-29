
docker pull grafana/grafana 
docker pull grafana/loki 
docker pull prom/prometheus 
docker pull prom/alertmanager 
docker pull wekasolutions/export

# set permissions so that the continer(s) can write to these directories
mkdir prometheus_data
chmod 755 prometheus_data/
chown 65534 prometheus_data/
chgrp 65534 prometheus_data/

mkdir prometheus_data
chmod 755 loki_data/
chown 10001 loki_data/
chgrp 10001 loki_data/
