%include        %{_topdir}/SPECS/version.inc
Name:		weka-mon
Version:	%{_tools_version}
Release:	1%{?dist}
Summary:	WEKA Monitoring (weka-mon)
BuildArch:	x86_64

License:	GPL
URL:		https://weka.io

# unset __brp_mangle_shebangs - it chokes on ansible files.
# (add a %) define __brp_mangle_shebangs /usr/bin/true


Requires:	coreutils
Requires:	tar
Requires:	podman

# These all get installed in /opt/tools
Source0:	weka-mon.tgz
#Source1:	containers.tar.gz

%define destdir	/opt/weka-mon

%description
WEKA Monitoring (weka-mon)

%build
echo Good

%install
rm -rf $RPM_BUILD_ROOT

install -d -m 0755 %{buildroot}%{destdir}
tar xvf %{SOURCE0} -C %{buildroot}%{destdir}

#install -m 0755 %{SOURCE1} %{buildroot}%{destdir}

# detach it from the git repo, if it exists
if [ -d %{buildroot}%{destdir}/.git ]; then
	rm -rf %{buildroot}%{destdir}/.git
fi

%post
podman load -i %{destdir}/containers.tar.gz
#%{destdir}/install.sh
# set permissions so that the continer(s) can write to these directories
mkdir -p %{destdir}/prometheus_data
chmod 755 %{destdir}/prometheus_data/
chown 65534 %{destdir}/prometheus_data/
chgrp 65534 %{destdir}/prometheus_data/

mkdir -p %{destdir}/loki_data
chmod 755 %{destdir}/loki_data/
chown 10001 %{destdir}/loki_data/
chgrp 10001 %{destdir}/loki_data/

# this is so the Grafana database persists between container restarts
chmod 755 %{destdir}/var_lib_grafana/ etc_grafana/
chown -R 472:0 %{destdir}/var_lib_grafana/ etc_grafana/

mkdir -p %{destdir}/logs
chown 472:472 %{destdir}/logs/
mkdir -p %{destdir}/.weka
chown 472:472 %{destdir}/.weka/

%files
%{destdir}/*

%changelog
* Thu Feb 13 2025 Vince Fleming <vince@weka.io>
-- 
