# 离线地理库与 Tor 出口快照

本目录随 `publish_asset_code.py` 打进发布包。登录路径**禁止**再访问公网 IP 查询接口。

## ip2region.xdb

- 用途：按 IP 查大概国家 / 省 / 运营商。
- 来源：<https://github.com/lionsoul2014/ip2region>（IPv4 xdb）。
- 更新：下载最新 `ip2region.xdb`（或仓库里的 IPv4 xdb 改名为本文件），覆盖后重新 publish。
- 缺失时：界面显示「未知」，接口不得 500。

## tor_exit_nodes.txt

- 用途：命中则打 `tor` 风险提示，**不会自动封**。
- 来源快照：<https://check.torproject.org/torbulkexitlist>
- 格式：一行一个 IPv4；`#` 开头为注释。
- 更新：重新下载覆盖本文件后 publish。快照会过期，只能当提示。

## 不要放进本目录

- 商业 VPN 库、MaxMind 账号、任何 API Key。
