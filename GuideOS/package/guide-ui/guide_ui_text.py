"""Shell-owned Unicode shaping; manifests retain role, weight and size."""
from PIL import ImageColor
from guide_unicode import UnicodeText


class RoleText(UnicodeText):
    def __init__(self, family, weight):
        super().__init__()
        self.family, self.weight = family, weight

    def _layout(self, text, size, width=None):
        layout = super()._layout(text, size, width)
        font = layout.get_font_description().copy()
        font.set_family({'serif':'Noto Serif, DejaVu Serif','sans':'Noto Sans, DejaVu Sans',
                         'mono':'Noto Sans Mono, DejaVu Sans Mono'}[self.family])
        font.set_weight(self.Pango.Weight.BOLD if self.weight=='bold' else self.Pango.Weight.NORMAL)
        layout.set_font_description(font)
        return layout


class SchemaText:
    def __init__(self):
        self.providers = {(f,w):RoleText(f,w) for f,w in
                          (('serif','bold'),('sans','regular'),('sans','bold'),('mono','regular'))}
        self.available = all(p.available for p in self.providers.values())

    def provider(self, spec):
        return self.providers[(spec['family'],spec['weight'])]

    def measure(self, text, spec):
        return self.provider(spec).measure(text,spec['size'])[0]

    def draw(self, canvas, xy, text, spec, color, anchor):
        rendered = self.provider(spec).render(text,spec['size'],ImageColor.getrgb(color))
        x,y=xy; anchor=anchor or 'lt'
        # Clip long labels at fixed role size; never reduce the typography.
        limit=440 if x==92 else 260 if x in (34,606) else 200 if anchor[0]=='m' else 180 if spec['family']=='serif' else 608
        if rendered.width>limit:rendered=rendered.crop((0,0,limit,rendered.height))
        if anchor[0]=='m':x-=rendered.width/2
        elif anchor[0]=='r':x-=rendered.width
        if anchor[-1]=='m':y-=rendered.height/2
        if canvas.image.mode=='RGBA':
            canvas.image.alpha_composite(rendered,(round(x),round(y)))
        else:canvas.image.paste(rendered,(round(x),round(y)),rendered)
