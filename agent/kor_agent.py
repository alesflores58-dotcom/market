#!/usr/bin/env python3
"""
kÖr Content Agent — genera historias y TikToks auténticos para @_korsv
Uso: python kor_agent.py foto1.jpg foto2.jpg ...
"""

import os
import sys
import json
import base64
import time
import argparse
import requests
from pathlib import Path
from anthropic import Anthropic

# ── Config ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
HIGGSFIELD_API_KEY = os.environ.get("HIGGSFIELD_API_KEY", "")
HIGGSFIELD_BASE = "https://api.higgsfield.ai"

client = Anthropic(api_key=ANTHROPIC_API_KEY)

KOR_SYSTEM_PROMPT = """Eres el agente de contenido de kÖr, marca de activewear premium de El Salvador (@_korsv).

IDENTIDAD DE MARCA:
- Nombre: kÖr (pronunciado "cor")
- Tagline: "Muévete con intención"
- Tono: auténtico, empoderador, cercano, NO corporativo, NO influencer genérico
- Audiencia: mujeres 18-35 El Salvador/Latinoamérica que entrenan en serio
- Colores: negro, blanco, toques vibrantes (fucsia, azul marino, ciruela)
- Nunca parecer IA. Siempre parecer real, humano, de una chica que entrena.

FORMATOS DE CONTENIDO:

HISTORIAS (Instagram Stories 1080×1920):
- S1 PRODUCTO PURO: foto de producto + nombre + precio + CTA "Disponible ahora"
- S2 LIFESTYLE RÁPIDO: foto acción + texto corto + sticker encuesta
- S3 MOTIVACIONAL: frase corta impactante + foto de fondo + logo kÖr
- S4 DETRÁS DE ESCENAS: foto casual sin filtros + caption honesto
- S5 UGC/REPOSTS: screenshot estilo repost con "@cliente" visible

TIKTOKS (vertical 9:16, 15-60 seg):
- F1 GET READY WITH ME: chica se prepara para entrenar con kÖr (autenticidad máxima)
- F2 ANTES/DESPUÉS OUTFIT: cambio de look, mismo lugar, corte directo
- F3 HAUL/UNBOXING: abrir paquete, probar, reacción real
- F4 WORKOUT HIGHLIGHT: ejercicios cortos, la ropa se ve en movimiento
- F5 LIFESTYLE VLOG: día normal entrenando, sin guión, sin filtros
- F6 TREND REACTION: adaptar trend viral al mundo fitness/kÖr
- F7 EDUCATIVO RÁPIDO: "3 razones por las que tu ropa de gym importa"
- F8 COMPARATIVA: kÖr vs ropa normal en el gym, sin nombrar marcas
- F9 DETRÁS DE ESCENAS MARCA: proceso de producción, equipo, etc.

REGLAS DE ORO:
1. Catálogo ≠ Lifestyle — fondo negro de estudio NO aplica aquí
2. Vida real: gym, espejo, exterior, golden hour, locker room
3. Hashtags: mezcla grande (#activewear, #fitness) + nicho (#gymgirlsv, #entrenamientofemenino) + marca (#kor, #korsv)
4. CTA siempre presente pero natural, no forzado
5. Emojis con moderación, solo los que usa una chica real
6. Precio siempre en dólares ($)

Cuando analices fotos, describe:
- Qué prenda se ve (color, tipo, ajuste)
- Qué formato(s) funcionan mejor para esa foto
- Variaciones Higgsfield a generar (prompts en inglés para la API)
- Caption completo listo para publicar (en español)
- Hashtags (20-25)
- Script de TikTok si aplica (con timestamps y acciones)
"""

# ── Higgsfield helpers ───────────────────────────────────────────────────────

def hf_upload(filepath: str) -> str:
    """Sube una foto a Higgsfield y retorna el media_id."""
    with open(filepath, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    ext = Path(filepath).suffix.lstrip(".")
    mime = f"image/{ext}" if ext in ("jpg","jpeg","png","webp") else "image/jpeg"

    resp = requests.post(
        f"{HIGGSFIELD_BASE}/v1/media/upload",
        headers={"Authorization": f"Bearer {HIGGSFIELD_API_KEY}", "Content-Type": "application/json"},
        json={"file": f"data:{mime};base64,{b64}", "filename": Path(filepath).name},
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["id"]


def hf_generate_image(prompt: str, reference_id: str = None, style: str = "lifestyle") -> dict:
    """Genera imagen lifestyle con Cinema Studio Image 2.5."""
    payload = {
        "model": "cinema-studio-image-2.5",
        "prompt": prompt,
        "aspect_ratio": "9:16",
        "num_outputs": 2,
    }
    if reference_id:
        payload["reference_image_id"] = reference_id
        payload["reference_strength"] = 0.75

    resp = requests.post(
        f"{HIGGSFIELD_BASE}/v1/image/generate",
        headers={"Authorization": f"Bearer {HIGGSFIELD_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=120
    )
    if resp.status_code != 200:
        return {"error": resp.text}
    return resp.json()


def hf_poll_job(job_id: str, max_wait: int = 120) -> dict:
    """Espera a que termine un job de Higgsfield."""
    for _ in range(max_wait // 5):
        time.sleep(5)
        resp = requests.get(
            f"{HIGGSFIELD_BASE}/v1/jobs/{job_id}",
            headers={"Authorization": f"Bearer {HIGGSFIELD_API_KEY}"},
            timeout=30
        )
        data = resp.json()
        if data.get("status") in ("completed", "failed"):
            return data
    return {"status": "timeout"}


# ── Claude analysis ──────────────────────────────────────────────────────────

def analyze_photos_with_claude(photo_paths: list[str]) -> dict:
    """Usa Claude para analizar las fotos y generar el plan de contenido."""
    content = []

    for path in photo_paths:
        with open(path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode()
        ext = Path(path).suffix.lstrip(".").lower()
        media_type = "image/jpeg" if ext in ("jpg","jpeg") else f"image/{ext}"
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64}
        })

    content.append({
        "type": "text",
        "text": f"""Analiza estas {len(photo_paths)} foto(s) que me entrega la dueña de kÖr.

Para cada foto genera:

1. ANÁLISIS DE FOTO
   - Qué se ve (prenda, color, contexto, calidad)
   - Formato recomendado (S1-S5 para stories, F1-F9 para TikTok)
   - Por qué funciona o qué falta

2. HISTORIAS (2-3 stories listas para publicar)
   - Tipo (S1-S5)
   - Texto overlay exacto (corto, máx 10 palabras)
   - Caption para compartir como historia
   - Sticker sugerido si aplica

3. TIKTOK SCRIPT (1 video)
   - Formato (F1-F9)
   - Duración sugerida
   - Script con timestamps:
     [0:00-0:03] Hook visual — qué se ve en pantalla
     [0:03-0:10] ...
   - Audio/música sugerida (tipo, mood)
   - Texto en pantalla

4. CAPTION INSTAGRAM POST
   - 3-4 líneas máx, tono real
   - 20-25 hashtags mezclados

5. PROMPTS HIGGSFIELD (en inglés)
   - 2 variaciones lifestyle para generar con Cinema Studio Image 2.5
   - Contextos: gym interior / exterior golden hour
   - Formato: "Fully clothed female fitness model wearing [describe exactamente lo que ves], [escenario real], natural lighting, authentic, not posed, shot on iPhone, real gym environment"

Responde en JSON con esta estructura:
{{
  "photos": [
    {{
      "filename": "foto1",
      "analysis": "...",
      "stories": [
        {{"type": "S1", "overlay_text": "...", "caption": "...", "sticker": "..."}}
      ],
      "tiktok": {{
        "format": "F1",
        "duration": "30s",
        "script": [...],
        "audio": "...",
        "on_screen_text": "..."
      }},
      "instagram_caption": "...",
      "hashtags": [...],
      "higgsfield_prompts": ["prompt1", "prompt2"]
    }}
  ],
  "content_calendar": "Sugerencia de cuándo publicar cada pieza esta semana"
}}"""
    })

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=KOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}]
    )

    text = response.content[0].text
    # Extraer JSON del response
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return {"raw": text, "photos": []}


# ── Output formatting ────────────────────────────────────────────────────────

def print_content_package(plan: dict, generate_images: bool = False):
    """Imprime el paquete de contenido de forma legible."""
    print("\n" + "═"*60)
    print("  kÖr CONTENT PACKAGE")
    print("═"*60)

    if "raw" in plan:
        print(plan["raw"])
        return

    photos = plan.get("photos", [])
    for i, photo in enumerate(photos, 1):
        print(f"\n📸 FOTO {i}: {photo.get('filename', '')}")
        print("─"*50)

        print(f"\n🔍 Análisis: {photo.get('analysis', '')}")

        print("\n📱 HISTORIAS:")
        for s in photo.get("stories", []):
            print(f"  [{s.get('type')}] \"{s.get('overlay_text')}\"")
            print(f"       Caption: {s.get('caption', '')}")
            if s.get("sticker"):
                print(f"       Sticker: {s.get('sticker')}")

        tiktok = photo.get("tiktok", {})
        if tiktok:
            print(f"\n🎬 TIKTOK [{tiktok.get('format')}] — {tiktok.get('duration')}:")
            for step in tiktok.get("script", []):
                if isinstance(step, dict):
                    print(f"  {step.get('time', '')} — {step.get('action', step)}")
                else:
                    print(f"  {step}")
            print(f"  Audio: {tiktok.get('audio', '')}")
            print(f"  Texto: {tiktok.get('on_screen_text', '')}")

        print(f"\n✍️  CAPTION:\n{photo.get('instagram_caption', '')}")

        hashtags = photo.get("hashtags", [])
        if hashtags:
            print(f"\n#️⃣  HASHTAGS: {' '.join('#'+h.lstrip('#') for h in hashtags)}")

        prompts = photo.get("higgsfield_prompts", [])
        if prompts and generate_images:
            print(f"\n🎨 Generando imágenes Higgsfield...")
            for j, prompt in enumerate(prompts, 1):
                print(f"  [{j}] {prompt[:80]}...")
                if HIGGSFIELD_API_KEY:
                    result = hf_generate_image(prompt)
                    job_id = result.get("id") or result.get("job_id")
                    if job_id:
                        print(f"  Job ID: {job_id} — esperando...")
                        final = hf_poll_job(job_id)
                        urls = final.get("outputs", [])
                        for url in urls:
                            print(f"  ✅ {url}")
                    else:
                        print(f"  ⚠️  {result.get('error', 'sin respuesta')}")
                else:
                    print(f"  ⚠️  Sin HIGGSFIELD_API_KEY — prompt guardado")
        elif prompts:
            print(f"\n🎨 PROMPTS HIGGSFIELD (corre con --generate para crear):")
            for j, p in enumerate(prompts, 1):
                print(f"  [{j}] {p}")

    if plan.get("content_calendar"):
        print(f"\n📅 CALENDARIO:\n{plan['content_calendar']}")

    print("\n" + "═"*60)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="kÖr Content Agent — genera stories y TikToks auténticos"
    )
    parser.add_argument("photos", nargs="+", help="Fotos a procesar (jpg/png)")
    parser.add_argument("--generate", action="store_true",
                        help="Generar imágenes con Higgsfield (requiere API key)")
    parser.add_argument("--json", action="store_true",
                        help="Output en JSON crudo")
    parser.add_argument("--save", metavar="FILE",
                        help="Guardar el plan en un archivo JSON")
    args = parser.parse_args()

    # Validar fotos
    valid_photos = []
    for p in args.photos:
        path = Path(p)
        if not path.exists():
            print(f"⚠️  No encontrado: {p}")
        elif path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            print(f"⚠️  Formato no soportado: {p}")
        else:
            valid_photos.append(str(path))

    if not valid_photos:
        print("❌ No hay fotos válidas para procesar.")
        sys.exit(1)

    if not ANTHROPIC_API_KEY:
        print("❌ Falta ANTHROPIC_API_KEY en variables de entorno.")
        sys.exit(1)

    print(f"🔄 Analizando {len(valid_photos)} foto(s) con Claude...")
    plan = analyze_photos_with_claude(valid_photos)

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(f"💾 Plan guardado en {args.save}")

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print_content_package(plan, generate_images=args.generate)


if __name__ == "__main__":
    main()
