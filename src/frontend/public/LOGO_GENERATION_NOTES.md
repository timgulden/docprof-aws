# Logo Generation Notes

## PNG Fallback Files Needed

The following PNG files need to be generated from the SVG files for browser fallback support:

1. **favicon-16px-light.png** - 16x16px PNG version of `favicon-16px-light.svg`
2. **favicon-16px-dark.png** - 16x16px PNG version of `favicon-16px-dark.svg`
3. **favicon.ico** - Legacy ICO format (can be generated from 16px PNG)

## Generation Methods

### Using ImageMagick
```bash
convert favicon-16px-light.svg -resize 16x16 favicon-16px-light.png
convert favicon-16px-dark.svg -resize 16x16 favicon-16px-dark.png
convert favicon-16px-light.png favicon.ico
```

### Using Inkscape
```bash
inkscape --export-type=png --export-width=16 --export-filename=favicon-16px-light.png favicon-16px-light.svg
inkscape --export-type=png --export-width=16 --export-filename=favicon-16px-dark.png favicon-16px-dark.svg
```

### Using Online Tools
- Upload SVG files to a converter like CloudConvert or Convertio
- Set output size to 16x16px
- Download PNG files

## Current Status

✅ SVG files created (light and dark variants)
✅ HTML configured with fallback links
⏳ PNG files need to be generated and placed in `/public` folder





