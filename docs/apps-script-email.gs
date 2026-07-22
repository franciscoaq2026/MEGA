/**
 * Envio de e-mail do Mega-Sena Stats via Google Apps Script (grátis, sem domínio).
 *
 * Este é um web app que roda na SUA conta Google e envia e-mail pelo seu Gmail.
 * O backend faz um POST com { to, subject, html } e este script dispara o e-mail.
 *
 * ── Como publicar (uma vez) ───────────────────────────────────────────────────
 * 1. Acesse https://script.google.com e crie um novo projeto.
 * 2. Apague o conteúdo padrão e cole TODO este arquivo.
 * 3. (Opcional) Ajuste REMETENTE_NOME abaixo.
 * 4. Clique em "Implantar" > "Nova implantação".
 *    - Tipo: "App da Web".
 *    - Executar como: "Eu (seu@gmail.com)".
 *    - Quem pode acessar: "Qualquer pessoa".
 * 5. Autorize o acesso quando o Google pedir (é a sua conta enviando e-mail).
 * 6. Copie a "URL do app da Web" (termina em /exec).
 * 7. No Vercel, em Settings > Environment Variables, crie:
 *      GOOGLE_SCRIPT_URL = a URL copiada
 *    (e faça um novo deploy).
 *
 * Cota grátis: ~100 e-mails/dia no Gmail comum — muito acima do necessário.
 */

var REMETENTE_NOME = 'Mega-Sena Stats';

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    if (!data.to || !data.subject) {
      return _json({ ok: false, error: 'to e subject são obrigatórios' });
    }
    MailApp.sendEmail({
      to: data.to,
      subject: data.subject,
      htmlBody: data.html || '',
      name: REMETENTE_NOME,
    });
    return _json({ ok: true });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

// Permite um teste rápido abrindo a URL no navegador (deve responder "ok").
function doGet() {
  return _json({ ok: true, service: 'megasena-email' });
}

function _json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
