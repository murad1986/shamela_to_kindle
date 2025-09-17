from scripts.shamela_to_epub import _parse_min_size, _maybe_convert_png_to_jpeg


def test_parse_min_size():
    assert _parse_min_size('600x800') == (600, 800)
    assert _parse_min_size(' 300X300 ') == (300, 300)
    assert _parse_min_size('bad') is None
    assert _parse_min_size('0x10') is None


def test_png_to_jpeg_conversion_optional():
    try:
        from PIL import Image
        import io
    except Exception:
        # Pillow not installed; function should return unchanged for png
        data = b'\x89PNG\r\n\x1a\n' + b'0'*100
        out, mime = _maybe_convert_png_to_jpeg(data, 'image/png')
        assert mime in ('image/png', 'image/jpeg')
        return
    # Create 1x1 PNG in-memory
    img = Image.new('RGB', (1,1), (255,255,255))
    buf = io.BytesIO(); img.save(buf, format='PNG'); data = buf.getvalue()
    out, mime = _maybe_convert_png_to_jpeg(data, 'image/png')
    assert mime == 'image/jpeg'
    assert isinstance(out, (bytes, bytearray)) and len(out) > 0
