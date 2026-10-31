// ===== Motor da conversa (CEEE) =====
// Lê: Entrada, Controle, Regras, Fila. Devolve um "plano" com:
//   fila: linhas da fila a salvar | controle: linha de controle a salvar | enviar: mensagens a mandar
const CONC = 'CEEE';
const TIMEOUT_MIN = 5;      // sem nenhuma mensagem nossa por 5 min com UC em andamento = sem resposta
const EXPIRA_MIN = 15;      // CEEE: depois de travar, espera o "sua sessão expirou" no máximo 15 min
const LIMITE_REPETICAO = 3; // mesma pergunta 3x seguidas = loop
const LIMITE_TRAVADAS = 2;  // travou 2x seguidas (loop/timeout) = para a fila
const LIMITE_REINICIOS = 2; // quantas vezes pode recomeçar a conversa da mesma UC

const norm = s => String(s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const agoraMs = Date.now();
const agoraTxt = new Date().toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' });

const entrada = $('Entrada').first().json;
const tipo = entrada.tipo || 'desconhecido';

const ctrlRow = $('Controle').all().map(i => i.json).find(r => r.id && r.concessionaria === CONC);
if (!ctrlRow) throw new Error(`Não existe linha "${CONC}" na data table controle_bot`);
const ctrl = { ...ctrlRow };

const regras = $('Regras').all().map(i => i.json)
  .filter(r => r.id && r.concessionaria === CONC && norm(r.ativo) !== 'nao' && String(r.gatilho || '').trim())
  .sort((a, b) => Number(a.ordem || 0) - Number(b.ordem || 0));

const filaRows = $('Fila').all().map(i => i.json).filter(r => r.id);
const atual = filaRows.find(r => r.situacao === 'em_andamento' || String(r.situacao || '').startsWith('aguardando_fim:')) || null;
const pendentes = filaRows.filter(r => r.situacao === 'pendente')
  .sort((a, b) => (Number(a.linha) || 0) - (Number(b.linha) || 0) || a.id - b.id);

const plano = { tipo, enviar: [], fila: [], controle: null, log: [] };
let ctrlMudou = false;
const setCtrl = obj => { Object.assign(ctrl, obj); ctrlMudou = true; };
const filaMap = new Map();
const setFila = (row, obj) => {
  const base = filaMap.get(row.id) || { ...row };
  Object.assign(base, obj, { atualizado_em: agoraTxt });
  filaMap.set(row.id, base);
  return base;
};
const linhaAtual = () => (atual ? (filaMap.get(atual.id) || atual) : null);
const enviar = texto => {
  if (String(texto ?? '').trim() === '') return;
  plano.enviar.push({ numero: ctrl.numero, texto: String(texto) });
  setCtrl({ ultimo_envio_ms: String(agoraMs) });
};
const preencher = (tpl, r) => {
  const v = {
    uc_nova: r?.uc_nova ?? '', site: r?.site ?? '', linha: r?.linha ?? '',
    cpf: ctrl.cpf ?? '', nome: ctrl.nome ?? '', email: ctrl.email ?? '', celular: ctrl.celular ?? '',
  };
  return String(tpl ?? '').replace(/\{(\w+)\}/g, (m, k) => (k in v ? String(v[k]) : m));
};
const extrair = (valor, texto) => {
  const v = String(valor ?? '');
  if (!v.toLowerCase().startsWith('regex:')) return v;
  const re = new RegExp(v.slice(6), 'i');
  const m = re.exec(norm(texto)) || re.exec(texto);
  return m ? (m[1] ?? m[0]) : '';
};
const extrairPrevisao = texto => {
  const achados = [...norm(texto).matchAll(/(\d{2}\/\d{2}\/\d{4})\s*(?:as|a)?\s*(\d{1,2}:\d{2})/g)];
  if (!achados.length) return '';
  const u = achados[achados.length - 1];
  return `${u[1]} ${u[2]}`;
};
// ultimo_gatilho guarda "R<n>|<gatilho>" quando a conversa da UC já foi reiniciada n vezes
const partes = g => {
  const m = /^R(\d+)\|([\s\S]*)$/.exec(String(g ?? ''));
  return m ? { n: Number(m[1]), g: m[2] } : { n: 0, g: String(g ?? '') };
};
const marcar = (r, gatilho, rep, extra = {}) => {
  const n = partes(r.ultimo_gatilho).n;
  return setFila(r, { ...extra, ultimo_gatilho: n ? `R${n}|${gatilho}` : gatilho, repeticoes: String(rep) });
};
const repeticao = regra => {
  const r = linhaAtual();
  return r && partes(r.ultimo_gatilho).g === regra.gatilho ? Number(r.repeticoes || 0) + 1 : 1;
};

function finalizarAtual(situacaoSeAberta) {
  const r = linhaAtual();
  if (!r) return;
  const s = String(r.situacao || '');
  if (s.startsWith('aguardando_fim:')) setFila(r, { situacao: s.slice('aguardando_fim:'.length) });
  else if (s === 'em_andamento') setFila(r, { situacao: situacaoSeAberta });
}
function iniciarProxima() {
  const prox = pendentes[0];
  if (!prox) {
    setCtrl({ status: 'concluido', pausado_ate_ms: '' });
    plano.log.push('fila concluída');
    return;
  }
  setFila(prox, { situacao: 'em_andamento', ultimo_gatilho: '', repeticoes: '0', msg_desconhecida: '' });
  setCtrl({ status: 'rodando', pausado_ate_ms: '' });
  enviar(ctrl.msg_inicial || 'ola');
  plano.log.push(`iniciando linha ${prox.linha} / site ${prox.site} / UC ${prox.uc_nova}`);
}
function travou(motivo) {
  const r = linhaAtual();
  if (r) {
    const s = String(r.situacao || '');
    setFila(r, { situacao: s.startsWith('aguardando_fim:') ? s.slice('aguardando_fim:'.length) : motivo });
  }
  const travadas = Number(ctrl.pausas_seguidas || 0) + 1;
  if (travadas >= LIMITE_TRAVADAS) {
    setCtrl({ status: 'parado', pausas_seguidas: String(travadas), pausado_ate_ms: '' });
    plano.log.push(`${motivo}: travou ${travadas}x seguidas, fila PARADA`);
    return;
  }
  if (CONC === 'CEEE') {
    // a Clara manda "sua sessão expirou" depois de ~10 min; esperamos por ela
    setCtrl({ status: 'aguardando_expiracao', pausado_ate_ms: String(agoraMs + EXPIRA_MIN * 60000), pausas_seguidas: String(travadas) });
  } else {
    const min = Number(ctrl.pausa_loop_min || 30);
    setCtrl({ status: 'pausado', pausado_ate_ms: String(agoraMs + min * 60000), pausas_seguidas: String(travadas) });
  }
  plano.log.push(`${motivo}: pausando`);
}

// ---------- iniciar (manual ou pelo Streamlit) ----------
if (tipo === 'iniciar') {
  finalizarAtual('interrompida');
  setCtrl({ pausas_seguidas: '0' });
  iniciarProxima();
}

// ---------- vigia (a cada minuto) ----------
if (tipo === 'tick') {
  const st = ctrl.status;
  const ate = Number(ctrl.pausado_ate_ms || 0);
  if ((st === 'pausado' || st === 'aguardando_expiracao') && ate && agoraMs >= ate) {
    finalizarAtual('sem_resposta');
    iniciarProxima();
  } else if (st === 'rodando' && atual) {
    const ult = Number(ctrl.ultimo_envio_ms || 0);
    if (ult && agoraMs - ult > TIMEOUT_MIN * 60000) {
      if (CONC === 'CEEE') travou('sem_resposta');
      else {
        travou('sem_resposta');
        if (ctrl.status === 'pausado') { setCtrl({ status: 'rodando', pausado_ate_ms: '' }); iniciarProxima(); }
      }
    }
  } else if (st === 'rodando' && !atual) {
    iniciarProxima();
  }
}

// ---------- mensagem recebida da concessionária ----------
if (tipo === 'mensagem') {
  setCtrl({ ultima_recebida_ms: String(agoraMs) });
  const texto = String(entrada.texto || '');
  const alvo = norm(texto + '\n' + (entrada.raw || ''));
  let regra = null;
  for (const r of regras) {
    const g = String(r.gatilho);
    let ok = false;
    if (norm(r.tipo) === 'regex') {
      try { const re = new RegExp(g, 'i'); ok = re.test(norm(texto)) || re.test(texto); } catch (e) { plano.log.push(`regex inválida na regra ${r.ordem}`); }
    } else ok = alvo.includes(norm(g));
    if (ok) { regra = r; break; }
  }
  const st = ctrl.status;
  const r = linhaAtual();
  plano.regra = regra ? `${regra.ordem} - ${regra.gatilho} -> ${regra.acao}` : '(nenhuma)';

  if (!['rodando', 'aguardando_expiracao', 'pausado'].includes(st)) {
    plano.log.push(`status "${st}": mensagem ignorada`);
  } else if (!regra) {
    if (r) setFila(r, { msg_desconhecida: texto.slice(0, 1500) });
    plano.log.push('mensagem desconhecida registrada');
  } else {
    const acao = norm(regra.acao);
    if (st !== 'rodando' && acao !== 'expirou') {
      plano.log.push(`fila ${st}: ignorando "${regra.gatilho}"`);
    } else if (acao === 'ignorar') {
      // aviso da concessionária, não precisa responder
    } else if (acao === 'expirou') {
      finalizarAtual('sem_resposta');
      iniciarProxima();
    } else if (!r) {
      plano.log.push(`sem UC em andamento para "${regra.gatilho}"`);
    } else if (acao === 'loop_sinal') {
      const n = repeticao(regra);
      marcar(r, regra.gatilho, n);
      if (n >= LIMITE_REPETICAO) travou('loop');
    } else if (acao === 'responder') {
      const n = repeticao(regra);
      if (n >= LIMITE_REPETICAO) travou('loop');
      else {
        marcar(r, regra.gatilho, n);
        enviar(preencher(regra.resposta, r));
      }
    } else if (acao === 'reiniciar') {
      // ex.: a Clara reforçou um chamado antigo do número; recomeça a conversa da MESMA UC
      const n = partes(r.ultimo_gatilho).n + 1;
      if (n > LIMITE_REINICIOS) travou('loop');
      else {
        setFila(r, { ultimo_gatilho: `R${n}|${regra.gatilho}`, repeticoes: '1' });
        enviar(preencher(regra.resposta, r));
        enviar(ctrl.msg_inicial || 'ola');
        plano.log.push(`recomeçando a conversa da mesma UC (${n}/${LIMITE_REINICIOS})`);
      }
    } else if (acao === 'reiniciar_se_no_meio') {
      // ex.: Clara manda "Olá! Eu sou a Clara..." no meio da conversa = ela reiniciou a sessão.
      // No começo da conversa é só a saudação normal: ignora.
      const p = partes(r.ultimo_gatilho);
      if (p.g) {
        const n = p.n + 1;
        if (n > LIMITE_REINICIOS) travou('loop');
        else {
          setFila(r, { ultimo_gatilho: `R${n}|`, repeticoes: '0' });
          enviar(ctrl.msg_inicial || 'ola');
          plano.log.push(`a concessionária reiniciou a conversa; recomeçando a mesma UC (${n}/${LIMITE_REINICIOS})`);
        }
      }
    } else if (acao === 'ja_aberto_e_proxima') {
      // ex.: "Pronto, reforçamos sua solicitação": anota protocolo já aberto e vai para a próxima UC
      marcar(r, regra.gatilho, 1, { protocolo: extrair(regra.valor_planilha, texto) || 'protocolo já aberto',
                                     previsao: '', situacao: 'ja_aberto' });
      setCtrl({ pausas_seguidas: '0' });
      enviar(preencher(regra.resposta, r));
      iniciarProxima();
    } else if (acao === 'protocolo' || acao === 'ja_aberto' || acao === 'uc_nao_encontrada') {
      const valor = acao === 'uc_nao_encontrada' ? '' : extrair(regra.valor_planilha, texto);
      const previsao = acao === 'uc_nao_encontrada' ? '' : extrairPrevisao(texto);
      marcar(r, regra.gatilho, 1, { protocolo: valor, previsao, situacao: `aguardando_fim:${acao}` });
      if (acao !== 'uc_nao_encontrada') setCtrl({ pausas_seguidas: '0' });
      if (acao !== 'uc_nao_encontrada' && !valor) plano.log.push('ATENÇÃO: regra de protocolo não conseguiu extrair o número');
      enviar(preencher(regra.resposta, r));
    } else if (acao === 'proxima' || acao === 'responder_e_proxima') {
      enviar(preencher(regra.resposta, r));
            // conversa terminou sem protocolo novo: a concessionária já tinha chamado aberto para a UC
      if (r.situacao === 'em_andamento') {
        setFila(r, { situacao: 'ja_aberto', protocolo: extrair(regra.valor_planilha, texto) || 'protocolo já aberto' });
      } else finalizarAtual('ja_aberto');
      iniciarProxima();
    } else {
      plano.log.push(`ação desconhecida "${regra.acao}" na regra ${regra.ordem}`);
    }
  }
}

plano.fila = [...filaMap.values()];
plano.controle = ctrlMudou ? ctrl : null;
return [{ json: plano }];
