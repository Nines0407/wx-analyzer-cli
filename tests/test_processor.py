from core.processor import (
    ContentProcessor,
    ImageItem,
    _is_image_url,
    IMAGE_EXTENSIONS,
    IMAGE_MD_RE,
    VIDEO_ELEMENT_RE,
    VIDEO_URL_RE,
)


SAMPLE_HTML = """<html><head><script>alert(1)</script><style>.a{color:red}</style></head>
<body><article>
<p>这是一篇好文章。</p>
<p>欢迎关注我们获取更多资讯。</p>
<img src="https://mmbiz.qpic.cn/photo/abc.png" />
<iframe data-src="https://mp.weixin.qq.com/video/123" />
<video src="https://example.com/video.mp4"></video>
<p>推荐阅读 <a href="/link">某文章</a></p>
<p>再见。</p>
</article></body></html>"""


class TestIsImageUrl:
    def test_png_extension(self):
        assert _is_image_url("https://cdn.example.com/photo.png") is True

    def test_jpg_extension(self):
        assert _is_image_url("https://cdn.example.com/photo.jpg") is True

    def test_webp_extension(self):
        assert _is_image_url("https://cdn.example.com/img.webp?w=100") is True

    def test_mmbiz_domain(self):
        assert _is_image_url("https://mmbiz.qpic.cn/mmbiz_jpg/abc/0?wx_fmt=jpeg") is True

    def test_mmbiz_qlogo_domain(self):
        assert _is_image_url("https://mmbiz.qlogo.cn/headimg/abc/0") is True

    def test_non_image_url(self):
        assert _is_image_url("https://example.com/video.mp4") is False

    def test_no_extension_no_known_domain(self):
        assert _is_image_url("https://example.com/api/image") is False

    def test_svg_extension(self):
        assert _is_image_url("https://cdn.example.com/icon.svg") is True

    def test_case_insensitive(self):
        assert _is_image_url("https://cdn.example.com/PHOTO.PNG") is True


class TestContentProcessorClean:
    def setup_method(self):
        self.processor = ContentProcessor()

    def test_removes_script_tags(self):
        html = '<p>text</p><script>bad()</script><p>more</p>'
        result = self.processor.clean(html)
        assert "script" not in result.lower()
        assert "bad()" not in result
        assert "text" in result
        assert "more" in result

    def test_removes_style_tags(self):
        html = '<style>.x{}</style><p>content</p>'
        result = self.processor.clean(html)
        assert "style" not in result.lower()
        assert "content" in result

    def test_removes_iframe_tags(self):
        html = '<p>text</p><iframe src="x"></iframe>'
        result = self.processor.clean(html)
        assert "iframe" not in result.lower()

    def test_removes_noscript_tags(self):
        html = '<noscript>no js</noscript><p>ok</p>'
        result = self.processor.clean(html)
        assert "noscript" not in result.lower()
        assert "no js" not in result
        assert "ok" in result

    def test_removes_svg_tags(self):
        html = '<svg><circle/></svg><p>text</p>'
        result = self.processor.clean(html)
        assert "svg" not in result.lower()
        assert "circle" not in result
        assert "text" in result

    def test_preserves_img_tags(self):
        html = '<p>text</p><img src="x.png" />'
        result = self.processor.clean(html)
        assert "img" in result.lower()

    def test_handles_multiline_tags(self):
        html = '<script>\nvar x=1;\nalert(x);\n</script><p>safe</p>'
        result = self.processor.clean(html)
        assert "script" not in result.lower()
        assert "alert" not in result
        assert "safe" in result


class TestContentProcessorHtmlToMarkdown:
    def setup_method(self):
        self.processor = ContentProcessor()

    def test_converts_html_to_markdown(self):
        html = "<h1>Title</h1><p>Hello world.</p>"
        markdown, anchors = self.processor.html_to_markdown(html)
        assert "Title" in markdown
        assert "Hello world" in markdown

    def test_extracts_image_anchors(self):
        html = '<img src="https://mmbiz.qpic.cn/photo/a.png" />'
        markdown, anchors = self.processor.html_to_markdown(html)
        assert len(anchors) >= 1

    def test_deduplicates_image_urls(self):
        html = '<img src="https://mmbiz.qpic.cn/a.png"/><img src="https://mmbiz.qpic.cn/a.png"/>'
        markdown, anchors = self.processor.html_to_markdown(html)
        url_count = sum(1 for a in anchors if "https://mmbiz.qpic.cn/a.png" == a[1])
        assert url_count <= 1

    def test_skips_non_image_urls_in_anchor_detection(self):
        html = '<img src="https://example.com/video.mp4" />'
        markdown, anchors = self.processor.html_to_markdown(html)
        assert len(anchors) == 0


class TestContentProcessorDetectMedia:
    def test_detects_img(self):
        html = '<div><img src="x.png"/></div>'
        assert ContentProcessor.detect_media_from_html(html) is True

    def test_detects_video_element(self):
        html = '<video src="x.mp4"></video>'
        assert ContentProcessor.detect_media_from_html(html) is True

    def test_detects_video_iframe(self):
        html = '<mp-common-videosnap data-src="x"></mp-common-videosnap>'
        assert ContentProcessor.detect_media_from_html(html) is True

    def test_no_media_returns_false(self):
        html = '<p>Plain text only.</p>'
        assert ContentProcessor.detect_media_from_html(html) is False

    def test_case_insensitive(self):
        html = '<IMG SRC="x.png">'
        assert ContentProcessor.detect_media_from_html(html) is True


class TestContentProcessorExtractVideoUrls:
    def test_extracts_iframe_src(self):
        html = '<iframe data-src="https://mp.weixin.qq.com/video/abc123"></iframe>'
        urls = ContentProcessor.extract_video_urls(html)
        assert "https://mp.weixin.qq.com/video/abc123" in urls

    def test_extracts_mp_common_videosnap(self):
        html = '<mp-common-videosnap src="https://example.com/v.mp4"></mp-common-videosnap>'
        urls = ContentProcessor.extract_video_urls(html)
        assert "https://example.com/v.mp4" in urls

    def test_deduplicates_video_urls(self):
        html = '<iframe data-src="https://x.com/a"></iframe><iframe src="https://x.com/a"></iframe>'
        urls = ContentProcessor.extract_video_urls(html)
        assert len(urls) == 1

    def test_no_video_returns_empty(self):
        html = "<p>No videos here</p>"
        assert ContentProcessor.extract_video_urls(html) == []


class TestContentProcessorRemoveNoise:
    def test_removes_recommended_reading(self):
        text = "正文内容。\n\n推荐阅读：请点击下方链接查看更多。\n\n结尾。"
        result = ContentProcessor.remove_noise(text)
        assert "推荐阅读" not in result
        assert "\u6b63\u6587" in result  # 正文
        assert "\u7ed3\u5c3e" in result  # 结尾

    def test_removes_follow_us(self):
        text = "内容。\n关注我们获取更多资讯，扫码关注。\n结束。"
        result = ContentProcessor.remove_noise(text)
        assert "关注我们" not in result

    def test_removes_advertisement(self):
        text = "文章内容。\n广告 点击购买。\n结尾。"
        result = ContentProcessor.remove_noise(text)
        assert "广告" not in result

    def test_preserves_normal_content(self):
        text = "这是一篇关于深度学习的技术文章，详细介绍了Transformer架构。"
        result = ContentProcessor.remove_noise(text)
        assert "深度学习" in result
        assert "Transformer" in result


class TestContentProcessorExtractImagesWithContext:
    def setup_method(self):
        self.processor = ContentProcessor()

    def test_extracts_context_around_image(self):
        markdown = (
            "前文" * 100 + "\n![img_0](https://mmbiz.qpic.cn/a.png)\n" + "后文" * 100
        )
        anchors = [("img_0", "https://mmbiz.qpic.cn/a.png")]
        items = self.processor.extract_images_with_context(markdown, anchors)
        assert len(items) == 1
        assert items[0].anchor_id == "img_0"
        assert items[0].url == "https://mmbiz.qpic.cn/a.png"
        assert "前文" in items[0].context
        assert "后文" in items[0].context

    def test_missing_anchor_returns_empty_context(self):
        markdown = "no image here\n"
        anchors = [("img_0", "https://mmbiz.qpic.cn/a.png")]
        items = self.processor.extract_images_with_context(markdown, anchors)
        assert len(items) == 1
        assert items[0].context == ""


class TestContentProcessorEmbedAnalysis:
    def setup_method(self):
        self.processor = ContentProcessor()

    def test_embeds_analysis_after_image(self):
        markdown = "![img_0](https://mmbiz.qpic.cn/a.png)"
        analyses = {"img_0": "This is an architecture diagram."}
        result = self.processor.embed_analysis(markdown, analyses)
        assert "AI 图像分析" in result
        assert "architecture diagram" in result
        assert "![img_0]" in result  # original anchor preserved

    def test_handles_missing_analysis(self):
        markdown = "![img_0](https://mmbiz.qpic.cn/a.png)"
        analyses = {"img_1": "something"}
        result = self.processor.embed_analysis(markdown, analyses)
        assert "AI 图像分析" not in result


class TestImageItem:
    def test_image_item_creation(self):
        item = ImageItem(anchor_id="img_0", url="https://example.com/a.png", context="ctx")
        assert item.anchor_id == "img_0"
        assert item.url == "https://example.com/a.png"
        assert item.context == "ctx"


class TestRegexPatterns:
    def test_image_md_re_matches(self):
        matches = IMAGE_MD_RE.findall("![alt](https://x.com/a.png)")
        assert len(matches) == 1
        assert matches[0][0] == "alt"
        assert matches[0][1] == "https://x.com/a.png"

    def test_video_element_re_matches(self):
        assert VIDEO_ELEMENT_RE.search('<video src="x"></video>') is not None
        assert VIDEO_ELEMENT_RE.search('<iframe data-src="https://x.com/video/123"></iframe>') is not None
        assert VIDEO_ELEMENT_RE.search("<mp-common-videosnap></mp-common-videosnap>") is not None

    def test_video_element_re_no_match(self):
        assert VIDEO_ELEMENT_RE.search("<p>text</p>") is None

    def test_video_url_re_extracts_src(self):
        urls = VIDEO_URL_RE.findall('<mp-common-videosnap data-src="https://x.com/v.mp4"></mp-common-videosnap>')
        assert "https://x.com/v.mp4" in urls

    def test_image_extensions_set(self):
        assert ".png" in IMAGE_EXTENSIONS
        assert ".jpg" in IMAGE_EXTENSIONS
        assert ".webp" in IMAGE_EXTENSIONS
        assert ".svg" in IMAGE_EXTENSIONS
        assert ".exe" not in IMAGE_EXTENSIONS
