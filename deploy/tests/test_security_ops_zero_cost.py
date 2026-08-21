"""零成本安全运营包 + 安全中心增强：TOTP / step-up / 地理 / 风险标签（无 DB）。"""
import os
import tempfile
import unittest

from app.core.step_up import StepUpStore
from app.core.totp_utils import generate_secret, provisioning_uri, totp_at, verify_totp
from app.utils.geoip import format_location, ip_kind, lookup_ip, parse_region_line
from app.utils.request_info import device_hash as make_device_hash
from app.utils.security_risk import (
    compute_risk_tags,
    is_common_country,
    join_tags,
    looks_like_datacenter,
    parse_tags,
    reset_tor_cache,
    timezone_mismatch,
)


class TestTotp(unittest.TestCase):
    def test_roundtrip(self):
        secret = generate_secret()
        code = totp_at(secret)
        self.assertTrue(verify_totp(secret, code))
        self.assertFalse(verify_totp(secret, "000000"))

    def test_uri(self):
        secret = generate_secret()
        uri = provisioning_uri(secret, "admin", issuer="测试系统")
        self.assertTrue(uri.startswith("otpauth://totp/"))
        self.assertIn("secret=", uri)


class TestStepUp(unittest.TestCase):
    def test_issue_verify(self):
        store = StepUpStore(expire_seconds=60)
        token, exp = store.issue(42)
        self.assertEqual(exp, 60)
        self.assertTrue(store.verify_and_keep(42, token))
        self.assertFalse(store.verify_and_keep(99, token))
        self.assertFalse(store.verify_and_keep(42, "bad"))


class _FakeRequest:
    def __init__(self, ua="Mozilla/5.0 Test", lang="zh-CN"):
        self.headers = {"user-agent": ua, "accept-language": lang}
        self.client = None


class TestGeoAndRisk(unittest.TestCase):
    def test_private_ip(self):
        self.assertEqual(ip_kind("127.0.0.1"), "private")
        self.assertEqual(ip_kind("192.168.1.8"), "private")
        self.assertEqual(ip_kind("10.0.0.2"), "private")
        geo = lookup_ip("127.0.0.1")
        self.assertEqual(geo["country"], "内网")

    def test_invalid_ip(self):
        self.assertEqual(ip_kind("not-an-ip"), "invalid")
        self.assertEqual(lookup_ip("not-an-ip")["country"], "未知")

    def test_parse_region_and_location(self):
        parsed = parse_region_line("中国|0|广东省|深圳市|电信")
        self.assertEqual(parsed["country"], "中国")
        self.assertEqual(parsed["region"], "广东省")
        self.assertEqual(parsed["isp"], "电信")
        self.assertEqual(format_location("中国", "广东省"), "中国 / 广东省")
        self.assertEqual(format_location("内网", "局域网"), "内网")

    def test_common_and_uncommon(self):
        self.assertTrue(is_common_country("中国"))
        self.assertTrue(is_common_country("CN"))
        self.assertTrue(is_common_country("内网"))
        self.assertFalse(is_common_country("美国"))
        tags = compute_risk_tags(country="美国", isp="Comcast")
        self.assertIn("uncommon_country", tags)
        self.assertNotIn("datacenter", tags)

    def test_datacenter_keyword(self):
        self.assertTrue(looks_like_datacenter("阿里云"))
        self.assertTrue(looks_like_datacenter("Amazon.com"))
        self.assertFalse(looks_like_datacenter("中国电信"))
        tags = compute_risk_tags(country="中国", isp="阿里云 BGP")
        self.assertIn("datacenter", tags)

    def test_tz_mismatch_only_obvious(self):
        self.assertTrue(timezone_mismatch("中国", "America/New_York"))
        self.assertFalse(timezone_mismatch("中国", "Asia/Shanghai"))
        self.assertFalse(timezone_mismatch("内网", "America/New_York"))
        tags = compute_risk_tags(country="中国", timezone="Europe/London")
        self.assertIn("tz_mismatch", tags)

    def test_tor_from_snapshot_file(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment\n1.2.3.4\n")
            reset_tor_cache()
            old = os.environ.get("TOR_EXIT_LIST_PATH")
            os.environ["TOR_EXIT_LIST_PATH"] = path
            try:
                # settings 已在 import 时读过环境变量；直接测文件解析
                from app.utils import security_risk as sr

                sr._tor_ips = None
                sr._tor_tried = False
                # 绕过 settings：把 load 指向临时文件
                orig = sr._tor_list_path
                sr._tor_list_path = lambda: path
                try:
                    tags = sr.compute_risk_tags(ip="1.2.3.4", country="荷兰")
                    self.assertIn("tor", tags)
                    tags2 = sr.compute_risk_tags(ip="8.8.8.8", country="美国")
                    self.assertNotIn("tor", tags2)
                finally:
                    sr._tor_list_path = orig
                    sr.reset_tor_cache()
            finally:
                if old is None:
                    os.environ.pop("TOR_EXIT_LIST_PATH", None)
                else:
                    os.environ["TOR_EXIT_LIST_PATH"] = old
        finally:
            os.remove(path)

    def test_no_auto_ban_contract(self):
        tags = compute_risk_tags(
            ip="1.2.3.4",
            country="美国",
            isp="DigitalOcean",
            timezone="Asia/Shanghai",
        )
        self.assertTrue(tags)
        # 本模块只返回标签字符串，没有封禁副作用
        self.assertTrue(all(isinstance(t, str) for t in tags))
        self.assertNotIn("ban", tags)
        text = join_tags(tags)
        self.assertNotIn("翻墙", text)
        self.assertNotIn("已确认", text)

    def test_device_hash_stable_and_sensitive(self):
        req = _FakeRequest()
        a = make_device_hash(req, client_hint="1920x1080", timezone="Asia/Shanghai", platform="Win32", languages="zh-CN")
        b = make_device_hash(req, client_hint="1920x1080", timezone="Asia/Shanghai", platform="Win32", languages="zh-CN")
        c = make_device_hash(req, client_hint="1366x768", timezone="Asia/Shanghai", platform="Win32", languages="zh-CN")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(a), 16)

    def test_parse_tags_whitelist(self):
        self.assertEqual(parse_tags("tor,datacenter,evil"), ["tor", "datacenter"])

    def test_xdb_public_ip_if_present(self):
        from app.utils import geoip as g

        xdb = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "ip2region.xdb"))
        if not os.path.isfile(xdb):
            self.skipTest("ip2region.xdb not shipped yet")
        g.reset_geoip_cache()
        geo = lookup_ip("114.114.114.114")
        self.assertTrue(geo["country"])
        self.assertNotEqual(geo["country"], "内网")
        # 中国公共 DNS 在离线库里应能出国家；库过旧则至少不是崩溃
        if geo["country"] not in {"未知", ""}:
            self.assertIn("中国", geo["country"])


if __name__ == "__main__":
    unittest.main()
