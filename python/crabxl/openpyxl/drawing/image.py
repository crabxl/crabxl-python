"""Image payload and placement settings for worksheet pictures."""

from io import BytesIO
from os import PathLike
from pathlib import Path

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

from .spreadsheet_drawing import _anchor_from_native, _anchor_input, _client_data_input


class Image:
    """A picture with a mutable anchor and pixel dimensions."""

    anchor = "A1"

    def __init__(self, img):
        from PIL import Image as PillowImage

        self.ref = img
        if isinstance(img, PillowImage.Image):
            self.width, self.height = img.size
            self.format = (img.format or "png").lower()
            self._payload = None
        else:
            if isinstance(img, (str, PathLike)):
                data = Path(img).read_bytes()
            else:
                data = self._read_file(img)
            with PillowImage.open(BytesIO(data)) as image:
                self.width, self.height = image.size
                self.format = image.format.lower()
                if self.format in ("gif", "jpeg", "png"):
                    self._payload = data
                else:
                    self._payload = self._encode_image(image, None)

    @staticmethod
    def _read_file(stream):
        offset = stream.tell()
        try:
            stream.seek(0)
            return stream.read()
        finally:
            stream.seek(offset)

    def _encode_image(self, image, original):
        if original is not None and self.format in ("gif", "jpeg", "png"):
            return self._read_file(original)
        with BytesIO() as output:
            image.save(output, format="PNG")
            self.format = "png"
            return output.getvalue()

    def _data(self):
        if self._payload is None:
            return self._encode_image(self.ref, getattr(self.ref, "fp", None))
        return self._payload

    @classmethod
    def _from_native(cls, prototype):
        image = cls(BytesIO(prototype.data()))
        image.anchor = _anchor_from_native(prototype.anchor())
        image._prototype = prototype
        return image

    def _native_input(self):
        value = (
            self._data(),
            f"image/{self.format}",
            _anchor_input(self.anchor, int(self.width * 9525), int(self.height * 9525)),
            _client_data_input(self.anchor),
        )
        prototype = getattr(self, "_prototype", None)
        return value if prototype is None else (*value, prototype)
