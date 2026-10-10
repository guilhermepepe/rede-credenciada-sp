# Rede Credenciada — São Paulo

Mapa interativo dos credenciados da rede odontológica na cidade de São Paulo,
sobre o Google Maps.

**Link:** https://guilhermepepe.github.io/rede-credenciada-sp/

## O que tem

- Os credenciados da capital posicionados por CEP, coloridos por tipo
  (clínica PJ, dentista PF, profissional vinculado).
- Busca por nome, rua, bairro ou CEP; filtros por tipo e por especialidade.
- Em cada ponto: endereço, CEP, contato, horários, especialidades e atalhos
  para Google Maps, Street View e rota.
- Camadas nativas do Google: ruas, satélite, híbrido, relevo, Street View e trânsito.

## Chave de API

A página usa a Maps JavaScript API, que exige uma chave. Ela fica em `config.js`.
A chave é pública por natureza nesse tipo de API — a proteção é restringi-la por
referenciador HTTP no Google Cloud Console para `https://guilhermepepe.github.io/*`.

Com `config.js` vazio, a página pede a chave a quem abrir e guarda no navegador.

## Dados

Extraídos do PDF "Encontre seu Dentista" de 09/10/2026. Coordenadas obtidas pelo
CEP (precisão de rua, não do número do imóvel).
