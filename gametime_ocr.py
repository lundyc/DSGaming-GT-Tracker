from PIL import Image, ImageOps
import easyocr

imageuri = input('Image: ')

left=39
top=0
right=260
bottom=152

def get_easy(detail_level):
    reader = easyocr.Reader(['en'], gpu=True)
    scale_factor = 2
    gray_image = ImageOps.grayscale(Image.open(imageuri)).crop((39,0,260,152))
    resized = gray_image.resize((gray_image.width * scale_factor, gray_image.height * scale_factor),
        resample=Image.Resampling.LANCZOS)
    resized.save('inprogress.png')
    easytext=reader.readtext('inprogress.png', detail=detail_level)
    return easytext

result = get_easy(0)
print(*result, sep='\n')