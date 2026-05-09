from core.security import is_safe_url


class TestIsSafeUrl:
    def test_normal_url_is_safe(self):
        assert is_safe_url("https://mp.weixin.qq.com/s/abc123") is True

    def test_mmbiz_image_url_is_safe(self):
        assert is_safe_url("https://mmbiz.qpic.cn/mmbiz_jpg/abc/0?wx_fmt=jpeg") is True

    def test_localhost_blocked(self):
        assert is_safe_url("http://localhost:8080/admin") is False

    def test_loopback_blocked(self):
        assert is_safe_url("http://127.0.0.1/api") is False

    def test_zero_ip_blocked(self):
        assert is_safe_url("http://0.0.0.0/") is False

    def test_cloud_metadata_blocked(self):
        assert is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_private_10_blocked(self):
        assert is_safe_url("http://10.0.0.1:8000/internal") is False

    def test_private_172_blocked(self):
        assert is_safe_url("http://172.16.0.1/secret") is False

    def test_private_192_blocked(self):
        assert is_safe_url("http://192.168.1.1/admin") is False

    def test_empty_url_not_safe(self):
        assert is_safe_url("") is False

    def test_invalid_url_not_safe(self):
        assert is_safe_url("not-a-url") is False

    def test_no_hostname_not_safe(self):
        assert is_safe_url("file:///etc/passwd") is False

    def test_https_public_ok(self):
        assert is_safe_url("https://example.com/image.png") is True

    def test_ftp_blocked_by_hostname_check(self):
        assert is_safe_url("ftp://10.0.0.1/file") is False

    def test_ipv6_loopback_blocked(self):
        assert is_safe_url("http://[::1]:8080/") is False

    def test_metadata_google_blocked(self):
        assert is_safe_url("http://metadata.google.internal/") is False
