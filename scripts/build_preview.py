"""Generate a portable HTML preview without APIs or external assets."""
import base64
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'studio' / 'web'


def build():
    html = (WEB / 'index.html').read_text()
    css = (WEB / 'style.css').read_text()
    font = base64.b64encode((WEB / 'fonts' / 'space-grotesk-latin.woff2').read_bytes()).decode()
    css = css.replace("url('/fonts/space-grotesk-latin.woff2')", f"url('data:font/woff2;base64,{font}')")
    css += '\n.preview-banner{padding:12px 16px;border:1px solid #537438;background:#192810;border-radius:8px;margin:20px 0 0;color:#c9e5b4;font-size:12px}.preview-banner strong{color:#c1ff61}.preview-banner span{color:#9db28d}\n'
    app = (WEB / 'app.js').read_text()
    html = re.sub(r'<link rel="preload"[^>]+>', '', html)
    html = html.replace('<link rel="stylesheet" href="/style.css">', '<style>' + css + '</style>')
    html = html.replace('<script src="/app.js" defer></script>', '')
    html = html.replace('<script src="/motion.js" defer></script>', '')
    html = html.replace('<script src="/template-render.js" defer></script>', '')
    html = html.replace('href="/" aria-label="Cria Studio início"', 'href="#editor" aria-label="Cria Studio início"')
    html = html.replace('</header>', '</header><div class="preview-banner" role="note"><strong>PRÉVIA HTML INTERATIVA</strong> <span>Explore templates, reedição e marca d’água com seu vídeo. Os cortes desta prévia são simulados; gerar MP4 exige o servidor.</span></div>', 1)
    html = html.replace('STUDIO / V.01', 'PRÉVIA HTML')
    html = html.replace('Processamento local<p>Seus vídeos são processados neste ambiente, sem APIs externas.</p>', 'Prévia local<p>Vídeos abertos apenas neste navegador. Exportações disponíveis na aplicação com servidor.</p>')
    scripts = (ROOT / 'scripts' / 'preview-adapter.js').read_text() + '\n' + app + '\n' + (WEB / 'template-render.js').read_text() + '\n' + (WEB / 'motion.js').read_text()
    html = html.replace('</body>', '<script>' + scripts.replace('</script', '<\\/script') + '</script>\n</body>')
    license_text = (WEB / 'fonts' / 'OFL.txt').read_text().replace('--', '—')
    html += '\n<!-- Space Grotesk font license:\n' + license_text + '\n-->\n'
    target = ROOT / 'preview.html'
    target.write_text(html)
    print(f'{target}: {target.stat().st_size} bytes')


if __name__ == '__main__':
    build()
