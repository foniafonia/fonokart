"""Genera con Piper TODO lo que dice FonoKart, para que nunca hable la voz del aparato.

Antes solo 27 textos tenían clip; el resto (letras, sílabas, media lista de
palabras y las frases de «Letras espejo») lo decía el sintetizador del
navegador, que suena distinto en cada tableta. José, 06/10/2026: «sigue
poniendo voces que no son las adecuadas».

  1. Saca de ../index.html las palabras, letras, sílabas y parejas del juego.
  2. Genera un MP3 por texto que falte (los que ya existen no se tocan).
  3. Reescribe en index.html el bloque VOZ_CLIPS (texto que dice el juego → fichero).

Voz: Piper (Open Home Foundation), modelo es_ES-sharvard-medium, hablante 1,
--length-scale 1.35. Licencia CC-BY 3.0. Modelo en ~/Developer/voz-logopedia/modelos.

Uso:   python3 voz/generar.py
"""
import json, pathlib, re, subprocess, sys, tempfile, unicodedata, wave

AQUI = pathlib.Path(__file__).resolve().parent
INDEX = AQUI.parent / 'index.html'
MODELO = pathlib.Path.home() / 'Developer/voz-logopedia/modelos/es_ES-sharvard-medium.onnx'
HABLANTE, VELOCIDAD = 1, 1.35
if not MODELO.exists():
    sys.exit('Falta el modelo de Piper: ' + str(MODELO))

html = INDEX.read_text()
leer = r"""const h=require('fs').readFileSync(process.argv[1],'utf8');
const coge=n=>{const m=h.match(new RegExp('const '+n+' = ([\\s\\S]*?);\\n'));return m?m[1]:'null'};
const o=new Function('return {PALABRAS:'+coge('PALABRAS')+',LETRAS:'+coge('LETRAS')+',CONSONANTES:'+coge('CONSONANTES')+',VOCALES:'+coge('VOCALES')+',PAIRS:'+coge('PAIRS')+'}')();
process.stdout.write(JSON.stringify(o));"""
D = json.loads(subprocess.run(['node', '-e', leer, str(INDEX)], capture_output=True, text=True, check=True).stdout)

NOMBRE = {'a': 'a', 'e': 'e', 'i': 'i', 'o': 'o', 'u': 'u', 'm': 'eme', 'p': 'pe', 's': 'ese', 'l': 'ele', 't': 'te',
          'n': 'ene', 'd': 'de', 'b': 'be', 'f': 'efe', 'g': 'ge', 'r': 'erre', 'c': 'ce', 'q': 'cu'}

def sin_tildes(t):
    t = t.replace('ñ', 'n')
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')

# clave (lo que el juego pasa a say(), en minúsculas) -> (fichero, texto que lee Piper)
clips = {}
for w, _ in D['PALABRAS']:
    k = w.lower(); clips[k] = (sin_tildes(k), k.capitalize() + '.')
letras = sorted(set(x.lower() for x in D['LETRAS']) | set(x for par in D['PAIRS'] for x in par))
for l in letras:
    clips[l] = (l if l in 'aeiou' else 'letra-' + l, NOMBRE[l].capitalize() + '.')
for c in D['CONSONANTES']:
    for v in D['VOCALES']:
        if c in 'GC' and v in 'EI':
            continue
        k = (c + v).lower()
        clips[k] = (k if (AQUI / (k + '.mp3')).exists() else 'sil-' + k, k.capitalize() + '.')
for l in sorted(set(x for par in D['PAIRS'] for x in par)):
    clips['muy bien, la ' + l] = ('bien-' + l, 'Muy bien, la ' + NOMBRE[l] + '.')
    clips['esa es la ' + l] = ('esa-' + l, 'Esa es la ' + NOMBRE[l] + '.')
clips['hola'] = ('hola', 'Hola.')

from piper import PiperVoice, SynthesisConfig
voz, hechos = None, 0
with tempfile.TemporaryDirectory() as tmp:
    for k, (f, texto) in clips.items():
        mp3 = AQUI / (f + '.mp3')
        if mp3.exists():
            continue
        if voz is None:
            voz = PiperVoice.load(str(MODELO), config_path=str(MODELO) + '.json')
            cfg = SynthesisConfig(speaker_id=HABLANTE, length_scale=VELOCIDAD)
        wav = pathlib.Path(tmp) / (f + '.wav')
        with wave.open(str(wav), 'wb') as w:
            voz.synthesize_wav(texto, w, syn_config=cfg)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav), '-ar', '22050', '-ac', '1',
                        '-c:a', 'libmp3lame', '-b:a', '64k', str(mp3)], check=True)
        hechos += 1

mapa = {k: f for k, (f, _) in sorted(clips.items())}
bloque = '/*VOZ_CLIPS:inicio — generado por voz/generar.py, no editar a mano*/\nconst VOZ_CLIPS = ' + json.dumps(mapa, ensure_ascii=False) + ';\n/*VOZ_CLIPS:fin*/'
if '/*VOZ_CLIPS:inicio' in html:
    html = re.sub(r'/\*VOZ_CLIPS:inicio[\s\S]*?/\*VOZ_CLIPS:fin\*/', lambda m: bloque, html)
else:
    viejo = re.search(r"const VOZ_CLIPS = \{[\s\S]*?\};", html)
    if not viejo:
        sys.exit('No encuentro VOZ_CLIPS en index.html')
    html = html[:viejo.start()] + bloque + html[viejo.end():]
INDEX.write_text(html)
print('textos: %d · generados: %d · en la carpeta: %d mp3' % (len(clips), hechos, len(list(AQUI.glob('*.mp3')))))
