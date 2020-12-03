# grafana-dashboards
Grafana Dashboard examples


Example Grafana Dashboards for Weka.  Use with the weka-metrics-exporter.

# Use:  

Install and configure the weka-metrics-exporter (http://github.com/weka/weka-metrics-exporter.git) 

Install and configure Prometheus (https://prometheus.io/)

Install and configure Grafana (https://grafana.com/)

Either follow the below directions for starting containers, or import the JSON files from the subdir var_lib_grafana_dashboards into an existing Grafana environment.


# Docker installation:
Installing Grafana, Prometheus, and weka-metrics-exporter in containers is an simple and convienient way to deploy these dashboards! Start by installing the metrics exporter (see above). The github page has a pre-built container under "Releases". Follow the instructions there. Then just install docker and do the following to get grafana and prometheus running - complete with these dashboards already installed!

install docker

```
docker pull grafana/grafana

docker pull prom/prometheus

docker pull wekasolutions/metrics-exporter:latest

cd grafana-dashboards

./set_permissions.sh

```
Start the Prometheus container:
```
docker run -d --net=host --restart unless-stopped --mount type=bind,source=$PWD/etc_prometheus/prometheus.yml,target=/etc/prometheus/prometheus.yml --mount type=bind,source=$PWD/prometheus_data,target=/prometheus prom/prometheus
```
Start the Grafana container:
```
docker run -d --net=host --restart unless-stopped --mount type=bind,source=$PWD/etc_grafana_provisioning/,target=/etc/grafana/provisioning --mount type=bind,source=$PWD/var_lib_grafana_dashboards/,target=/var/lib/grafana/dashboards grafana/grafana
```

Please refer to instructions on http://guthub.com/weka/weka-metrics-exporter for running the exporter container

# Optional Alertmanager configuration

Examples for Slack and PagerDuty are provided.

Edit the etc_alertmanger/alertmanager.yml file to add your keys for Slack or PagerDuty, and configure one of the two services.

Then run the Prometheus Alertmanager.

Example docker image use:
```
docker pull prom/alertmanager
docker run -d --restart unless-stopped --network=host   --mount type=bind,source=/dev/log,target=/dev/log   --mount type=bind,source=/etc/hosts,target=/etc/hosts   --mount type=bind,source=$PWD/etc_alertmanager,target=/etc/alertmanager   prom/alertmanager --log.level=debug --config.file="/etc/alertmanager/alertmanager.yml"
```

# Optional Grafana Loki (log database) configuration

Example docker image use:
```
docker pull grafana/loki:2.0.0
docker run \
    -d \
    --restart unless-stopped \
    -p 3100:3100 \
    -v /dev/log:/dev/log \
    -v $(pwd)/etc_loki:/etc/loki \
    -v $(pwd)/loki_data:/loki \
    grafana/loki:2.0.0 \
    -config.file=/etc/loki/loki-config.yaml
```
