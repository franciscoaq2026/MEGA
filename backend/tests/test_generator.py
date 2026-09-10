import random

from app import generator, lotteries

DRAWS = [
    {"concurso": i, "data": f"2024-01-{i:02d}", "dezenas": sorted(random.Random(i).sample(range(1, 61), 6))}
    for i in range(1, 51)
]

# Histórico sintético por loteria, para os testes que precisam de dezenas dentro
# do volante certo (a Lotofácil vai só até 25).
DRAWS_POR_LOTERIA = {
    "mega": DRAWS,
    "lofa": [
        {"concurso": i, "data": f"2024-01-{i:02d}",
         "dezenas": sorted(random.Random(i).sample(range(1, 26), 15))}
        for i in range(1, 51)
    ],
}


def _check_valid(jogo, k):
    assert len(jogo) == k
    assert len(set(jogo)) == k
    assert all(1 <= n <= 60 for n in jogo)
    assert jogo == sorted(jogo)


def test_todas_estrategias_geram_jogos_validos():
    rng = random.Random(1)
    for estrategia in generator.GERADORES:
        for k in (6, 10, 20):
            jogos = generator.gerar(DRAWS, estrategia, jogos=3, dezenas=k, rng=rng)
            assert len(jogos) == 3
            for j in jogos:
                _check_valid(j["dezenas"], k)
                assert j["soma"] == sum(j["dezenas"])


def test_aleatorio_funciona_sem_historico():
    jogos = generator.gerar([], "aleatorio", jogos=2, dezenas=6, rng=random.Random(2))
    assert len(jogos) == 2


def test_balanceado_respeita_restricoes():
    rng = random.Random(3)
    for _ in range(20):
        jogo = generator.balanceado(rng, DRAWS, 6)
        soma = sum(jogo)
        pares = sum(1 for n in jogo if n % 2 == 0)
        assert 141 <= soma <= 225  # 183 ± 42
        assert 2 <= pares <= 4


def test_padrao_popular():
    assert generator.padrao_popular([1, 5, 9, 13, 17, 21])  # PA e todas ≤ 31
    assert generator.padrao_popular([10, 20, 30, 40, 50, 60])  # mesma coluna
    assert generator.padrao_popular([1, 2, 3, 4, 33, 58])  # 4 consecutivos
    assert not generator.padrao_popular([2, 14, 27, 38, 45, 59])
    senas = {(4, 5, 30, 33, 41, 52)}
    assert generator.padrao_popular([4, 5, 30, 33, 41, 52], senas)


def test_anti_rateio_evita_padroes():
    rng = random.Random(4)
    jogos = generator.gerar(DRAWS, "aleatorio", jogos=10, dezenas=6, anti_rateio=True, rng=rng)
    for j in jogos:
        assert j["padroes_populares"] == []


def test_odds_valores_conhecidos():
    o6 = generator.odds(6)
    assert o6["combos_simples"] == 1
    assert o6["faixas"]["sena"]["one_in"] == 50063860
    assert o6["faixas"]["quina"]["one_in"] == 154518
    assert o6["faixas"]["quadra"]["one_in"] == 2332

    o15 = generator.odds(15)
    assert o15["combos_simples"] == 5005
    # "1 em N" trunca (convenção da Caixa): 50.063.860/5.005 = 10.002,77
    assert o15["faixas"]["sena"]["one_in"] == int(50063860 / 5005) == 10002

    # 20 dezenas (máximo atual da Caixa): caso do bolão da Aldeota no 3010.
    #
    # Aqui as duas fontes oficiais divergem entre si, e não há convenção que
    # satisfaça as duas: o valor exato é 1.291,63, e a Mega costuma ser
    # divulgada como "1 em 1.292" (arredondando), enquanto a tabela da
    # Lotofácil publica 691 para 691,80 (truncando). O app trunca em toda
    # parte, porque a linha que o usuário de fato confere é a aposta simples
    # da Lotofácil — impressa no bilhete dele — e não esta, de R$ 232.560.
    # Não "conserte" isto para 1292 sem trocar a convenção em `_um_em`.
    o20 = generator.odds(20)
    assert o20["combos_simples"] == 38760
    assert o20["faixas"]["sena"]["one_in"] == 1291


def test_distribuicao_acertos_lotofacil():
    """A régua que julga um resultado já saído. Valores fechados da
    hipergeométrica 15 de 25 (esperado = 15·15/25 = 9)."""
    d = generator.distribuicao_acertos(15, "lofa")
    assert d["esperado"] == 9.0
    assert d["mais_provavel"] == 9
    assert abs(sum(l["prob"] for l in d["linhas"]) - 1) < 1e-12
    por_acerto = {l["acertos"]: l for l in d["linhas"]}
    # 15 acertos = 1 em 3.268.760, a chance da faixa principal
    assert round(1 / por_acerto[15]["prob"]) == 3268760
    # premiar (>= 11) sai em ~10,6% dos jogos — 1 em 9
    assert d["premiado"]["one_in"] == 9
    assert round(d["premiado"]["pct"], 2) == 10.59
    # caudas estritas somam 1 com a própria linha
    l9 = por_acerto[9]
    assert abs(l9["p_menos"] + l9["prob"] + l9["p_mais"] - 1) < 1e-12
    # abaixo de 5 acertos é impossível: sobram só 10 dezenas fora do sorteio
    assert min(por_acerto) == 5


def test_distribuicao_acertos_mega_e_aposta_maior():
    d6 = generator.distribuicao_acertos(6)
    assert d6["esperado"] == 0.6
    assert d6["mais_provavel"] == 0  # o resultado mais comum é não acertar nada
    assert abs(sum(l["prob"] for l in d6["linhas"]) - 1) < 1e-12
    # cada dezena a mais no bilhete sobe o esperado em sorteadas/total
    d20 = generator.distribuicao_acertos(20)
    assert d20["esperado"] == 2.0
    d18 = generator.distribuicao_acertos(18, "lofa")
    assert d18["esperado"] == 10.8
    assert d18["mais_provavel"] == 11


def test_avaliar_acertos_veredito():
    """Régua de 1 desvio-padrão: na Lotofácil simples (9 ± 1,22), 8 a 10 é o
    normal; 11 para cima é acima do esperado; 7 para baixo, abaixo."""
    niveis = {h: generator.avaliar_acertos(h, 15, "lofa")["nivel"] for h in range(5, 16)}
    assert [niveis[h] for h in (5, 6, 7)] == ["abaixo"] * 3
    assert [niveis[h] for h in (8, 9, 10)] == ["tipico"] * 3
    assert [niveis[h] for h in (11, 12, 13, 14, 15)] == ["acima"] * 5

    a9 = generator.avaliar_acertos(9, 15, "lofa")
    assert a9["diferenca"] == 0.0
    assert a9["faixa_tipica"] == [7.8, 10.2]
    # ~34% dos jogos fariam pior e ~34% melhor: 9 acertos é o meio da curva
    assert round(a9["pct_pior"]) == 34
    assert round(a9["pct_melhor"]) == 34


def test_piso_sobreposicao():
    """Casa dos pombos: dois bilhetes de k dezenas dividem >= 2k - total."""
    mega = lotteries.LOTERIAS["mega"]
    lofa = lotteries.LOTERIAS["lofa"]
    assert generator.piso_sobreposicao(6, mega) == 0   # 6+6 cabem em 60
    assert generator.piso_sobreposicao(15, lofa) == 5  # 15+15 em 25 -> 5 forçadas
    assert generator.piso_sobreposicao(20, lofa) == 15
    # o piso é atingível de fato: nenhum par de bilhetes fica abaixo dele
    for lot, k in (("mega", 6), ("lofa", 15)):
        cfg = lotteries.LOTERIAS[lot]
        piso = generator.piso_sobreposicao(k, cfg)
        jogos = generator.gerar(
            DRAWS_POR_LOTERIA[lot], "aleatorio", 4, k,
            rng=random.Random(7), loteria=lot, espalhar=True,
        )
        r = generator.resumo_sobreposicao(jogos, k, lot)
        assert r["maxima"] >= piso
        assert r["piso"] == piso


def test_resumo_sobreposicao():
    jogos = [{"dezenas": [1, 2, 3, 4, 5, 6]}, {"dezenas": [1, 2, 3, 40, 50, 60]}]
    r = generator.resumo_sobreposicao(jogos, 6, "mega")
    assert (r["maxima"], r["media"], r["piso"], r["no_piso"]) == (3, 3.0, 0, False)
    # bilhetes idênticos: o pior caso possível
    iguais = [{"dezenas": [1, 2, 3, 4, 5, 6]}] * 2
    assert generator.resumo_sobreposicao(iguais, 6, "mega")["maxima"] == 6
    # um bilhete só não tem com quem se sobrepor
    assert generator.resumo_sobreposicao(jogos[:1], 6, "mega") is None


def test_espalhar_reduz_sobreposicao_na_lotofacil():
    """Espalhar tem efeito real, mas limitado pelo piso de 5 da Lotofácil."""
    kw = dict(loteria="lofa", draws=DRAWS_POR_LOTERIA["lofa"])
    solto = generator.gerar(
        kw["draws"], "aleatorio", 5, 15, rng=random.Random(11),
        loteria="lofa", espalhar=False,
    )
    esp = generator.gerar(
        kw["draws"], "aleatorio", 5, 15, rng=random.Random(11),
        loteria="lofa", espalhar=True,
    )
    r_solto = generator.resumo_sobreposicao(solto, 15, "lofa")
    r_esp = generator.resumo_sobreposicao(esp, 15, "lofa")
    assert r_esp["media"] < r_solto["media"]
    assert r_esp["maxima"] >= 5  # o piso não pode ser furado


def test_limiar_sobreposicao():
    """Zona gratuita: enquanto dois bilhetes não PODEM premiar juntos,
    P(levar algo) = N·p exatamente, o teto. Ver limiar_sobreposicao."""
    mega = lotteries.LOTERIAS["mega"]
    lofa = lotteries.LOTERIAS["lofa"]
    assert generator.limiar_sobreposicao(mega) == 1   # 2·4 − 6 − 1
    assert generator.limiar_sobreposicao(lofa) == 6   # 2·11 − 15 − 1

    # a conta que sustenta o limiar: no limiar, prêmio duplo é impossível;
    # uma dezena acima, passa a ser possível
    for cfg in (mega, lofa):
        f, S = min(cfg["faixas"]), cfg["sorteadas"]
        limiar = generator.limiar_sobreposicao(cfg)
        assert limiar + S < 2 * f       # soma máxima de acertos não alcança 2 faixas
        assert (limiar + 1) + S >= 2 * f

    # na Lotofácil o piso (5) cabe na zona gratuita (6): com 2 bilhetes o ótimo
    # é alcançável. Na Mega, piso 0 <= limiar 1, idem.
    assert generator.piso_sobreposicao(15, lofa) <= generator.limiar_sobreposicao(lofa)
    assert generator.piso_sobreposicao(6, mega) <= generator.limiar_sobreposicao(mega)
    # com 20 dezenas por bilhete na Lotofácil o piso sobe a 15: zona inalcançável
    assert generator.piso_sobreposicao(20, lofa) > generator.limiar_sobreposicao(lofa)


def test_resumo_sobreposicao_zona_gratuita():
    # Mega: dois bilhetes dividindo 1 dezena estão na zona gratuita (limiar 1)
    um = [{"dezenas": [1, 2, 3, 4, 5, 6]}, {"dezenas": [6, 10, 20, 30, 40, 50]}]
    r = generator.resumo_sobreposicao(um, 6, "mega")
    assert r["maxima"] == 1
    assert r["limiar"] == 1
    assert r["sem_custo"] is True
    assert r["no_piso"] is False  # não está no piso (0), mas custa a mesma coisa
    assert r["otimo_possivel"] is True
    # duas dezenas em comum já permitem prêmio duplo -> sai da zona
    duas = [{"dezenas": [1, 2, 3, 4, 5, 6]}, {"dezenas": [5, 6, 20, 30, 40, 50]}]
    assert generator.resumo_sobreposicao(duas, 6, "mega")["sem_custo"] is False


def test_odds_carteira_reage_ao_espalhar():
    """A tela mostrava o valor de bilhetes SOLTOS mesmo com espalhar ligado.
    Espalhar não muda o prêmio principal nem o retorno médio, mas muda a
    chance de levar algo — e a função tem de refletir isso."""
    solto = generator.odds_carteira(5, "mega")
    esp = generator.odds_carteira(5, "mega", espalhar=True)
    assert esp["qualquer"]["prob"] > solto["qualquer"]["prob"]
    assert esp["qualquer_solto"] == solto["qualquer"]
    # faixas individuais (inclusive o prêmio principal) não mudam
    assert esp["faixas"] == solto["faixas"]
    assert esp["custo_estimado"] == solto["custo_estimado"]

    # Mega: espalhado é EXATAMENTE N·p (zona gratuita), não 1-(1-p)^N
    p = generator.odds(6, loteria="mega")["qualquer"]["prob"]
    assert esp["metodo"] == "exato"
    assert abs(esp["qualquer"]["prob"] - 5 * p) < 1e-15
    assert solto["qualquer"]["prob"] < 5 * p  # o independente fica abaixo do teto

    # 1 bilhete não tem o que espalhar
    um = generator.odds_carteira(1, "mega", espalhar=True)
    assert um["espalhar"] is False
    assert um["metodo"] == "independente"


def test_odds_carteira_lotofacil_usa_tabela_enumerada():
    """Na Lotofácil a zona gratuita não é alcançável com 3+ bilhetes, então o
    valor espalhado vem da tabela medida por enumeração exata."""
    cfg = lotteries.LOTERIAS["lofa"]
    tabela = cfg.get("carteira_espalhada") or {}
    assert tabela, "tabela de carteira espalhada ausente"
    p = generator.odds(15, loteria="lofa")["qualquer"]["prob"]
    for n, valor in tabela.items():
        solto = 1 - (1 - p) ** n
        assert solto <= valor <= min(1.0, n * p) + 1e-9, f"N={n} fora dos limites teóricos"
    r = generator.odds_carteira(12, "lofa", espalhar=True)
    assert r["metodo"] == "enumerado"
    assert r["qualquer"]["prob"] > r["qualquer_solto"]["prob"]


def test_zona_gratuita_da_mega_fura_em_lotes_grandes():
    """Bug real corrigido: a Mega só garante sobreposição <= limiar (a 'zona
    gratuita') para N pequeno — o gerador greedy fura isso bem antes do teto
    matemático ingênuo (N*p <= 1, que só travaria perto de N=2298). Este teste
    prova que a sobreposição real ultrapassa o limiar num N bem menor, para
    justificar por que `odds_carteira` não pode confiar cegamente nisso."""
    mega = lotteries.LOTERIAS["mega"]
    limiar = generator.limiar_sobreposicao(mega)
    jogos = generator.gerar([], "aleatorio", 100, 6, False, loteria="mega", espalhar=True, rng=random.Random(7))
    overlap = generator.resumo_sobreposicao(jogos, 6, "mega")
    assert overlap["maxima"] > limiar, (
        "se isto passar a ser falso, o gerador melhorou e o teste seguinte "
        "(que depende de furar a zona gratuita) precisa de um N maior"
    )


def test_odds_carteira_mega_nao_superestima_alem_da_zona_gratuita():
    """O bug: com bilhetes reais cuja sobreposição já ultrapassa o limiar, o
    código antigo continuava devolvendo 'exato' = N*p — superestimando a
    chance real em ~0,15pp num lote de 200 (contra simulação de 3 milhões de
    sorteios). Agora tem que medir, nunca devolver mais que o teto de Boole,
    e não pode mais alegar 'exato'."""
    p_uma = generator.odds(6, loteria="mega")["qualquer"]["prob"]
    jogos = generator.gerar([], "aleatorio", 100, 6, False, loteria="mega", espalhar=True, rng=random.Random(7))
    bilhetes = [set(j["dezenas"]) for j in jogos]
    r = generator.odds_carteira(100, "mega", espalhar=True, bilhetes=bilhetes, rng=random.Random(1))
    assert r["metodo"] == "simulado"
    teto = 100 * p_uma
    assert r["qualquer"]["prob"] <= teto + 1e-12, "nunca pode superar o teto de Boole (N*p)"
    # a chance medida tem que ficar perto do teto (a correção é pequena aqui:
    # só ~10% dos pares excedem o limiar, e cada um custa muito pouco), não
    # despencar como despencaria uma correção de 2ª ordem mal calibrada.
    assert teto * 0.9 < r["qualquer"]["prob"] <= teto


def test_odds_carteira_respeita_zona_gratuita_com_bilhetes_reais():
    """Caso feliz sem regressão: com N pequeno (sobreposição real ainda dentro
    do limiar), continua exato e idêntico a N*p — não precisa simular nada."""
    p_uma = generator.odds(6, loteria="mega")["qualquer"]["prob"]
    jogos = generator.gerar([], "aleatorio", 10, 6, False, loteria="mega", espalhar=True, rng=random.Random(1))
    bilhetes = [set(j["dezenas"]) for j in jogos]
    r = generator.odds_carteira(10, "mega", espalhar=True, bilhetes=bilhetes)
    assert r["metodo"] == "exato"
    assert abs(r["qualquer"]["prob"] - 10 * p_uma) < 1e-15


def test_odds_carteira_lotofacil_alem_da_tabela_ainda_mostra_ganho_real():
    """Bug real corrigido: acima de N=20 (fora da tabela medida por
    enumeração), a Lotofácil caía sempre no independente — 'espalhar' virava
    um no-op silencioso (mesmo número com a opção ligada ou desligada), na
    faixa que o teto de jogos por geração (100, depois 200) passou a
    alcançar de verdade. Agora tem que continuar refletindo um ganho real."""
    n = 42
    assert n not in lotteries.LOTERIAS["lofa"]["carteira_espalhada"], "N já teria entrada exata na tabela"
    espalhado = generator.odds_carteira(n, "lofa", espalhar=True)
    solto = generator.odds_carteira(n, "lofa", espalhar=False)
    assert espalhado["metodo"] == "simulado"
    assert espalhado["qualquer"]["prob"] > solto["qualquer"]["prob"] + 0.005, (
        "espalhar precisa mostrar um ganho real e não trivial acima de N=20"
    )


def test_odds_carteira_prioriza_tabela_medida_mesmo_com_bilhetes_reais():
    """A tabela por enumeração exata é mais precisa que simular sobre um lote
    específico — tem que vencer mesmo quando `bilhetes` reais são passados."""
    jogos = generator.gerar([], "aleatorio", 12, 15, False, loteria="lofa", espalhar=True, rng=random.Random(3))
    bilhetes = [set(j["dezenas"]) for j in jogos]
    r = generator.odds_carteira(12, "lofa", espalhar=True, bilhetes=bilhetes)
    assert r["metodo"] == "enumerado"
    assert r["qualquer"]["prob"] == lotteries.LOTERIAS["lofa"]["carteira_espalhada"][12]


def test_odds_carteira_nao_tenta_gerar_previa_gigante():
    """Acima do teto prático de jogos (200, o limite do endpoint /generate),
    não vale a pena arriscar montar um lote de prévia O(N²) só para estimar a
    prévia ao vivo — cai no independente (conservador, nunca superestima) em
    vez de travar a requisição."""
    import time

    t0 = time.time()
    r = generator.odds_carteira(5000, "mega", espalhar=True)
    assert time.time() - t0 < 1.0
    assert r["metodo"] == "independente"


def test_fallback_nao_emite_bilhete_duplicado():
    """Bilhete repetido no mesmo lote é dinheiro gasto sem cobrir nada novo.
    O laço principal já barrava isso via `vistos`, mas o caminho de fallback
    (quando nenhum candidato passa nos filtros) sorteava um jogo novo SEM
    consultar a trava. Com Mega/Lotofácil isso é inalcançável (o espaço de
    combinações é grande demais), então o teste usa uma loteria sintética
    minúscula — 20 combinações possíveis — onde o caminho é exercitado de
    verdade: antes da correção, 4% dos lotes saíam com duplicata."""
    lotteries.LOTERIAS["_mini_teste"] = {
        "code": "_mini_teste", "nome": "Mini", "min_num": 1, "max_num": 6,
        "total": 6, "escolher": 3, "max_escolher": 4, "sorteadas": 3,
        "faixas": {3: "cheia", 2: "dupla"}, "fonte": "mini", "cols": 3,
        "preco": 1.0, "avancada": False, "premios_fixos": {},
        "consecutivos_populares": 99,
    }
    try:
        for seed in range(60):
            jogos = generator.gerar(
                [], "aleatorio", 20, 3, anti_rateio=False,
                loteria="_mini_teste", espalhar=False, rng=random.Random(seed),
            )
            chaves = [tuple(j["dezenas"]) for j in jogos]
            assert len(chaves) == len(set(chaves)), (
                f"semente {seed}: lote com bilhete duplicado — o fallback furou o `vistos`"
            )
    finally:
        del lotteries.LOTERIAS["_mini_teste"]
