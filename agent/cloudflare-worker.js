/**
 * kÖr Studio — Puente (proxy) hacia la API de Claude.
 *
 * Anthropic NO permite llamadas directas desde una página web (CORS).
 * Este Worker recibe la petición de la app, le agrega la API key en el
 * servidor, y se la pasa a Claude. Así el iPhone nunca habla directo con
 * Anthropic y la key queda escondida aquí (segura).
 *
 * --- CÓMO PUBLICARLO (gratis, ~5 min) ---
 * 1. Entra a https://dash.cloudflare.com  → crea cuenta gratis
 * 2. Menú izquierdo: "Workers & Pages" → "Create" → "Create Worker"
 * 3. Ponle un nombre (ej. kor-studio) → "Deploy"
 * 4. "Edit code" → borra todo y pega ESTE archivo completo → "Deploy"
 * 5. Settings → Variables and Secrets → "Add":
 *      Type: Secret
 *      Name: ANTHROPIC_API_KEY
 *      Value: tu key sk-ant-...
 *    → Deploy
 * 6. Copia la URL del Worker (algo como
 *    https://kor-studio.TUNOMBRE.workers.dev) y pégala en la app (⚙).
 */

export default {
  async fetch(request, env) {
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'content-type',
      'Access-Control-Max-Age': '86400',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: cors });
    }
    if (request.method !== 'POST') {
      return new Response('Solo POST', { status: 405, headers: cors });
    }
    if (!env.ANTHROPIC_API_KEY) {
      return new Response(
        JSON.stringify({ error: { message: 'Falta configurar ANTHROPIC_API_KEY en el Worker (Settings → Variables and Secrets).' } }),
        { status: 500, headers: { ...cors, 'content-type': 'application/json' } }
      );
    }

    const body = await request.text();

    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body,
    });

    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { ...cors, 'content-type': 'application/json' },
    });
  },
};
