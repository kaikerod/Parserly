import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { ExternalLink, FileSearch, Mail, ShieldCheck } from "lucide-react";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: "Política de Privacidade | Parserly",
  description:
    "Entenda como o Parserly coleta, usa, compartilha e protege dados pessoais conforme a LGPD."
};

const CONTROLLER_NAME = "Parserly";
const CONTROLLER_REGISTRATION = "Sem CNPJ no momento";
const CONTROLLER_OPERATION = "Operação digital no Brasil";
const SITE_DOMAIN = "https://www.parserly.com.br";
const PRIVACY_CONTACT = "contato.parserly@gmail.com";
const PRIVACY_CHANNEL = "Canal de privacidade Parserly";
const LAST_UPDATED = "30 de maio de 2026";

const summaryRows = [
  {
    theme: "Quem controla seus dados",
    detail: `${CONTROLLER_NAME}, ${CONTROLLER_REGISTRATION}, ${CONTROLLER_OPERATION}`
  },
  {
    theme: "Para que usamos dados",
    detail:
      "Para operar o site, autenticar usuários, analisar currículos, gerar relatórios, salvar histórico, processar pagamentos, enviar comunicações, proteger a plataforma e cumprir obrigações legais"
  },
  {
    theme: "Principais dados tratados",
    detail:
      "Dados de conta, contato, login, currículo enviado, conteúdo extraído do currículo, relatórios de análise, histórico, dados de pagamento, cookies, IP, dispositivo e registros de segurança"
  },
  {
    theme: "Compartilhamento",
    detail:
      "Podemos compartilhar dados com fornecedores de hospedagem, banco de dados, e-mail, autenticação, pagamento, IA, analytics/monitoramento, assessores profissionais e autoridades públicas quando necessário"
  },
  {
    theme: "Cookies",
    detail:
      "Usamos cookies necessários para funcionamento, segurança e sessão. Cookies não necessários, se usados, devem ser informados e dependerão de consentimento quando exigido"
  },
  {
    theme: "Seus direitos",
    detail:
      "Você pode pedir confirmação, acesso, correção, anonimização, bloqueio, eliminação, portabilidade, informações sobre compartilhamento, revogação de consentimento, oposição e outros direitos previstos na LGPD"
  },
  {
    theme: "Canal de privacidade",
    detail: PRIVACY_CONTACT
  }
];

const scopeItems = [
  "visitantes do site",
  "usuários que criam conta ou fazem login",
  "pessoas que enviam currículos para análise",
  "pessoas que realizam pagamentos ou compram créditos de análise",
  "pessoas que entram em contato conosco por canais de atendimento"
];

const directDataItems = [
  "dados de identificação e contato, como nome, e-mail, telefone e dados incluídos em mensagens enviadas a nós",
  "dados de conta e login, como e-mail usado para magic link, identificadores de autenticação e informações básicas de perfil quando você usa login social",
  "currículo e documentos enviados para análise, incluindo nome do arquivo, texto extraído, experiências profissionais, formação, habilidades, certificações, objetivos profissionais e demais informações que você inserir no documento",
  "comunicações de suporte, dúvidas, reclamações, solicitações de direitos e respectivos anexos",
  "informações necessárias para pagamento ou compra de créditos, como identificador da transação, status do pagamento, valor, data e dados mínimos de conciliação"
];

const automaticDataItems = [
  "endereço IP",
  "data e horário de acesso",
  "identificadores de sessão",
  "tipo de navegador, sistema operacional, dispositivo e configurações técnicas",
  "páginas acessadas, ações realizadas e eventos de uso",
  "registros de segurança, prevenção a fraude e diagnóstico de falhas",
  "cookies e tecnologias semelhantes, conforme explicado na seção de cookies"
];

const thirdPartyDataItems = [
  "provedores de autenticação, como Google, quando você usa login social",
  "provedores de pagamento, como Mercado Pago, para confirmação de pagamento, status de transação e liberação de créditos",
  "provedores de e-mail, hospedagem, monitoramento, analytics ou segurança, conforme contratados",
  "autoridades públicas, quando houver obrigação legal, ordem válida ou exercício regular de direitos"
];

const purposeRows = [
  [
    "Criar, autenticar e manter sua conta",
    "e-mail, identificador de usuário, sessão, login social",
    "Execução de contrato ou procedimentos preliminares; legítimo interesse para segurança; consentimento quando aplicável"
  ],
  [
    "Receber e analisar currículo",
    "arquivo enviado, texto extraído, dados profissionais, relatório gerado",
    "Execução de contrato ou procedimentos preliminares; consentimento quando aplicável, inclusive para dados sensíveis inseridos pelo usuário"
  ],
  [
    "Gerar pontuação, diagnóstico e recomendações",
    "conteúdo do currículo, critérios de análise, resultado da IA",
    "Execução de contrato ou procedimentos preliminares; legítimo interesse na melhoria do serviço, quando aplicável"
  ],
  [
    "Salvar histórico de análises",
    "relatórios, pontuações, datas, nome do arquivo",
    "Execução de contrato; legítimo interesse em permitir consulta posterior; cumprimento de obrigação legal quando aplicável"
  ],
  [
    "Processar pagamentos e créditos",
    "identificador da transação, status, valor, data, dados de conciliação",
    "Execução de contrato; cumprimento de obrigação legal/regulatória; exercício regular de direitos"
  ],
  [
    "Enviar e-mails transacionais",
    "e-mail, eventos de login, mensagens de confirmação",
    "Execução de contrato; legítimo interesse; consentimento quando aplicável"
  ],
  [
    "Atender solicitações e suporte",
    "nome, e-mail, mensagem, anexos, histórico de atendimento",
    "Execução de contrato; legítimo interesse; cumprimento de obrigação legal"
  ],
  [
    "Proteger a plataforma e prevenir fraude",
    "IP, logs, dispositivo, sessão, eventos de segurança",
    "Legítimo interesse; cumprimento de obrigação legal; exercício regular de direitos"
  ],
  [
    "Cumprir leis, ordens ou defender direitos",
    "dados necessários ao caso concreto",
    "Cumprimento de obrigação legal/regulatória; exercício regular de direitos"
  ],
  [
    "Enviar comunicações promocionais, se houver",
    "nome, e-mail, preferências",
    "Consentimento ou legítimo interesse, conforme o caso e com opção de descadastro"
  ],
  [
    "Realizar analytics e melhoria do site, se houver",
    "cookies, eventos de uso, dados agregados",
    "Consentimento para cookies não necessários quando exigido; legítimo interesse para medições estritamente necessárias e proporcionais"
  ]
];

const sharingItems = [
  "fornecedores de hospedagem, infraestrutura, banco de dados, armazenamento, cache e segurança contratados para operar o Parserly",
  "provedores de autenticação, como Google",
  "provedores de envio de e-mail, como Resend",
  "provedores de pagamento, como Mercado Pago",
  "provedores de IA, modelos ou roteadores de modelos, como OpenRouter, quando necessário para gerar a análise solicitada",
  "ferramentas de analytics, monitoramento, logs, atendimento ou suporte usadas para operar, proteger e melhorar o serviço",
  "consultores, contadores, advogados, auditores e demais assessores profissionais",
  "autoridades públicas, órgãos reguladores, Poder Judiciário ou terceiros quando houver obrigação legal, ordem válida, investigação, defesa de direitos ou prevenção a fraude"
];

const cookieRows = [
  [
    "Necessários",
    "Permitir navegação, autenticação, sessão, segurança, prevenção a fraude e funcionamento básico",
    "Não dependem de consentimento quando estritamente necessários"
  ],
  [
    "Preferências",
    "Lembrar escolhas do usuário, como idioma ou configurações",
    "Consentimento quando exigido; no momento, não usamos cookies de preferências não necessários"
  ],
  [
    "Analytics/desempenho",
    "Entender uso do site, medir falhas e melhorar experiência",
    "Consentimento quando exigido para cookies não necessários"
  ],
  [
    "Marketing/publicidade",
    "Medir campanhas, personalizar anúncios ou criar públicos",
    "Consentimento prévio, específico e revogável, quando utilizados"
  ]
];

const cookieManagementItems = [
  "pelo banner ou painel de preferências de cookies, quando disponível em nosso site",
  "pelas configurações do seu navegador",
  `entrando em contato pelo canal ${PRIVACY_CONTACT}`
];

const retentionRows = [
  ["Dados de conta", "Enquanto a conta estiver ativa e pelo prazo necessário para cumprir obrigações legais, resolver disputas ou preservar direitos"],
  ["Currículos enviados", "Enquanto forem necessários para entregar a análise, manter o histórico solicitado pelo usuário ou cumprir obrigações legais"],
  ["Relatórios e histórico de análise", "Enquanto a conta estiver ativa ou até solicitação válida de eliminação, observadas hipóteses legais de conservação"],
  ["Dados de pagamento e conciliação", "Pelo prazo necessário para cumprimento de obrigações legais, contábeis, fiscais e para prevenção a fraude"],
  ["Logs de segurança e acesso", "Pelo prazo necessário para segurança, prevenção a fraude, diagnóstico de falhas e preservação de direitos"],
  ["Solicitações de suporte e direitos LGPD", "Pelo prazo necessário para atender a solicitação, comprovar resposta e preservar direitos"],
  ["Cookies", "Conforme a expiração técnica de cada cookie; cookies de autenticação e segurança duram apenas pelo tempo necessário à sessão e à proteção da plataforma"]
];

const rightsItems = [
  "confirmar se tratamos seus dados pessoais",
  "acessar seus dados pessoais",
  "corrigir dados incompletos, inexatos ou desatualizados",
  "solicitar anonimização, bloqueio ou eliminação de dados desnecessários, excessivos ou tratados em desconformidade com a LGPD",
  "solicitar portabilidade dos dados a outro fornecedor, quando aplicável e conforme regulamentação da ANPD",
  "pedir a eliminação de dados tratados com base no consentimento, observadas as hipóteses legais de conservação",
  "receber informações sobre entidades públicas e privadas com as quais compartilhamos seus dados",
  "receber informações sobre a possibilidade de não fornecer consentimento e sobre as consequências da negativa",
  "revogar consentimento, quando o tratamento se basear nessa hipótese legal",
  "opor-se a tratamento realizado em desconformidade com a LGPD",
  "solicitar revisão de decisões tomadas unicamente com base em tratamento automatizado de dados pessoais, quando aplicável",
  "apresentar petição à Autoridade Nacional de Proteção de Dados (ANPD), se entender que seus direitos não foram atendidos"
];

const securityItems = [
  "controle de acesso e autenticação",
  "criptografia em trânsito e, quando aplicável, em repouso",
  "segregação de ambientes e uso de credenciais protegidas",
  "registros de segurança e monitoramento",
  "limitação de acesso por necessidade",
  "validação de uploads e restrições de tipo/tamanho de arquivo",
  "exclusão ou limitação de arquivos temporários quando não forem mais necessários",
  "contratos e instruções de tratamento com fornecedores",
  "revisão periódica de práticas de segurança"
];

const contactRows = [
  ["Controlador", CONTROLLER_NAME],
  ["CNPJ", CONTROLLER_REGISTRATION],
  ["Atendimento", CONTROLLER_OPERATION],
  ["Site", SITE_DOMAIN],
  ["Canal de privacidade", PRIVACY_CHANNEL],
  ["E-mail", PRIVACY_CONTACT],
  ["Canal adicional", "Não disponível no momento"]
];

export default function PrivacyPolicyPage() {
  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-5 text-paper sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-96 bg-[linear-gradient(115deg,rgba(109,93,252,0.22),transparent_42%),linear-gradient(250deg,rgba(69,255,115,0.12),transparent_36%)]" />

      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <nav className="flex w-full flex-wrap items-center justify-between gap-3 border-b border-line/55 pb-4 text-xs text-paper/60">
          <Link href="/dashboard" className="focus-ring flex min-w-0 items-center gap-3 rounded-md">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-violet text-paper shadow-glow">
              <FileSearch className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="flex min-w-0 items-center gap-3">
              <span className="font-display text-base font-semibold text-paper">Parserly</span>
              <span className="hidden text-paper/30 sm:inline">/</span>
              <span className="hidden truncate sm:inline">Política de Privacidade</span>
            </span>
          </Link>

          <div className="flex w-full flex-wrap items-center justify-between gap-2 sm:w-auto sm:justify-end">
            <a
              href="#contato-dpo"
              className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 font-semibold text-paper/75 transition hover:border-acid/45 hover:bg-fog"
            >
              <Mail className="h-4 w-4" aria-hidden="true" />
              Contato LGPD
            </a>
            <Link
              href="/dashboard"
              className="focus-ring inline-flex min-h-10 items-center gap-2 rounded-md border border-line/70 bg-night px-3 py-2 font-semibold text-paper/75 transition hover:border-acid/45 hover:bg-fog"
            >
              Dashboard
            </Link>
          </div>
        </nav>

        <header className="grid min-w-0 gap-6 border-b border-line/55 pb-8 lg:grid-cols-[1fr_22rem] lg:items-end">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-md border border-line/70 bg-graphite/80 px-3 py-1.5 text-xs font-bold uppercase text-paper/70 shadow-tool backdrop-blur">
              <ShieldCheck className="h-4 w-4 text-acid" aria-hidden="true" />
              LGPD e privacidade
            </div>

            <h1 className="mt-5 max-w-4xl font-display text-5xl font-semibold leading-none text-paper md:text-6xl">
              Política de <span className="accent-text">Privacidade</span>
            </h1>

            <p className="mt-4 text-sm font-semibold text-paper/70">
              Última atualização: <span className="font-mono text-acid">{LAST_UPDATED}</span>
            </p>

            <p className="mt-5 max-w-3xl text-sm leading-7 text-paper/68">
              Esta Política de Privacidade explica, de forma simples e transparente, como{" "}
              <PolicyValue>{CONTROLLER_NAME}</PolicyValue> ("Parserly", "nós" ou "nosso"), projeto
              sem CNPJ no momento e com operação digital no Brasil, trata dados pessoais de pessoas
              que acessam ou usam o site <PolicyValue>{SITE_DOMAIN}</PolicyValue> e os serviços
              relacionados à análise de currículos.
            </p>
          </div>

          <div className="min-w-0 rounded-md border border-acid/30 bg-acid/10 p-4 text-sm leading-6 text-paper shadow-tool">
            <p className="font-semibold text-acid">Canal de privacidade</p>
            <p className="mt-2 text-paper/70">
              Se você tiver dúvidas ou quiser exercer seus direitos como titular de dados, fale pelo
              nosso canal de privacidade no e-mail{" "}
              <a className="focus-ring rounded-sm text-paper underline decoration-acid/50 underline-offset-4" href="#contato-dpo">
                {PRIVACY_CONTACT}
              </a>
              .
            </p>
          </div>
        </header>

        <section id="resumo-rapido" aria-labelledby="resumo-title" className="min-w-0 space-y-4">
          <SectionHeading
            eyebrow="Resumo rápido"
            title="O que você precisa saber"
            id="resumo-title"
          />
          <PolicyTable headers={["Tema", "O que você precisa saber"]} rows={summaryRows.map((row) => [row.theme, row.detail])} />
        </section>

        <PolicySection
          id="introducao"
          eyebrow="1"
          title="Introdução: quem somos e nosso compromisso"
        >
          <p>
            O Parserly é uma plataforma que ajuda pessoas a avaliar currículos para compatibilidade
            com sistemas ATS, gerando pontuação, diagnóstico e recomendações de melhoria.
          </p>
          <p>
            Levamos privacidade a sério. Tratamos dados pessoais somente para finalidades legítimas,
            informadas e compatíveis com os serviços que oferecemos, observando a{" "}
            <ExternalPolicyLink href="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm">
              Lei Geral de Proteção de Dados Pessoais
            </ExternalPolicyLink>{" "}
            (Lei nº 13.709/2018, "LGPD") e demais normas aplicáveis.
          </p>
          <p>Esta Política se aplica a:</p>
          <PolicyList items={scopeItems} />
        </PolicySection>

        <PolicySection
          id="dados-coletados"
          eyebrow="2"
          title="Quais dados pessoais coletamos e como coletamos"
        >
          <p>
            Coletamos dados de três formas principais: quando você nos fornece informações, quando
            o uso do serviço gera informações automaticamente e quando terceiros nos enviam dados
            necessários para autenticação, pagamento ou operação do serviço.
          </p>

          <Subsection title="2.1. Dados que você nos fornece diretamente">
            <p>Podemos coletar:</p>
            <PolicyList items={directDataItems} />
            <Notice>
              Importante: não pedimos que você inclua dados sensíveis no currículo. Ainda assim, um
              currículo pode conter, por escolha do próprio usuário, dados como foto, informações de
              saúde, deficiência, filiação sindical, origem racial ou étnica, religião, opinião
              política ou outros dados sensíveis. Recomendamos remover qualquer dado sensível que
              não seja necessário para a análise desejada. Quando o tratamento de dados sensíveis
              for necessário ou exigido por lei, aplicaremos a base legal adequada, incluindo
              consentimento específico quando cabível.
            </Notice>
          </Subsection>

          <Subsection title="2.2. Dados coletados automaticamente durante a navegação">
            <p>Quando você acessa o site, podemos coletar:</p>
            <PolicyList items={automaticDataItems} />
          </Subsection>

          <Subsection title="2.3. Dados recebidos de terceiros">
            <p>Podemos receber dados de terceiros quando isso for necessário para entregar o serviço, por exemplo:</p>
            <PolicyList items={thirdPartyDataItems} />
          </Subsection>
        </PolicySection>

        <PolicySection
          id="finalidades-bases-legais"
          eyebrow="3"
          title="Para quais finalidades tratamos seus dados e quais bases legais usamos"
        >
          <p>
            Tratamos dados pessoais para finalidades específicas. A tabela abaixo resume as
            principais operações e bases legais da LGPD que podem ser aplicáveis.
          </p>
          <PolicyTable headers={["Finalidade", "Exemplos de dados", "Base legal LGPD"]} rows={purposeRows} />
          <p>
            Sempre que usarmos legítimo interesse, avaliaremos se o tratamento é necessário,
            proporcional e compatível com as expectativas do titular, respeitando seus direitos e
            liberdades fundamentais.
          </p>
        </PolicySection>

        <PolicySection id="compartilhamento" eyebrow="4" title="Compartilhamento de dados com terceiros">
          <p>
            Não vendemos seus dados pessoais. Podemos compartilhar dados apenas quando necessário
            para as finalidades descritas nesta Política.
          </p>
          <p>Podemos compartilhar dados com:</p>
          <PolicyList items={sharingItems} />
          <p>
            Quando terceiros atuarem como operadores em nosso nome, exigiremos que tratem os dados
            conforme nossas instruções, com medidas de segurança adequadas e sem uso para
            finalidades próprias incompatíveis.
          </p>
          <p>
            Alguns fornecedores podem estar localizados fora do Brasil ou usar infraestrutura
            internacional. Nesses casos, a transferência internacional de dados observará a LGPD e
            mecanismos juridicamente adequados, como cláusulas contratuais, normas corporativas,
            decisões de adequação ou outros instrumentos permitidos pela legislação aplicável.
          </p>
        </PolicySection>

        <PolicySection id="cookies" eyebrow="5" title="Política de cookies e rastreamento">
          <p>
            Cookies são pequenos arquivos ou identificadores armazenados no seu navegador ou
            dispositivo. Eles ajudam o site a funcionar, manter sua sessão, proteger a plataforma e,
            quando autorizado, medir desempenho ou personalizar a experiência.
          </p>

          <Subsection title="5.1. Tipos de cookies que podemos usar">
            <PolicyTable headers={["Categoria", "Finalidade", "Consentimento"]} rows={cookieRows} />
            <Notice>
              Atualmente, não utilizamos cookies não necessários no momento.
            </Notice>
          </Subsection>

          <Subsection title="5.2. Como gerenciar cookies">
            <p>Você pode gerenciar cookies:</p>
            <PolicyList items={cookieManagementItems} />
            <p>
              Se você bloquear cookies necessários, algumas áreas do site podem não funcionar
              corretamente. Cookies não necessários devem permanecer desativados até que você dê
              consentimento, quando o consentimento for a base legal aplicável.
            </p>
          </Subsection>
        </PolicySection>

        <PolicySection id="retencao" eyebrow="6" title="Por quanto tempo mantemos os dados">
          <p>
            Mantemos dados pessoais somente pelo tempo necessário para cumprir as finalidades desta
            Política, respeitar prazos legais ou regulatórios, preservar direitos, prevenir fraude e
            manter registros de segurança.
          </p>
          <p>Os prazos específicos devem ser preenchidos conforme a operação:</p>
          <PolicyTable headers={["Categoria", "Prazo esperado"]} rows={retentionRows} />
          <p>
            Quando os dados deixarem de ser necessários, serão eliminados, anonimizados ou mantidos
            apenas nas hipóteses permitidas pela LGPD, como cumprimento de obrigação legal, estudo
            por órgão de pesquisa, transferência a terceiro observados os requisitos legais, ou uso
            exclusivo do controlador com dados anonimizados.
          </p>
        </PolicySection>

        <PolicySection id="direitos" eyebrow="7" title="Seus direitos como titular de dados">
          <p>Você pode exercer os direitos previstos na LGPD, especialmente:</p>
          <PolicyList items={rightsItems} />
          <p>
            Para exercer seus direitos, envie uma solicitação para{" "}
            <a className="focus-ring rounded-sm text-acid underline decoration-acid/50 underline-offset-4" href="#contato-dpo">
              {PRIVACY_CONTACT}
            </a>{" "}
            com o assunto <PolicyValue>Solicitação LGPD</PolicyValue>.
          </p>
          <p>
            Para proteger sua privacidade, poderemos solicitar informações adicionais para confirmar
            sua identidade antes de responder. Responderemos dentro dos prazos legais aplicáveis e
            explicaremos quando não for possível atender total ou parcialmente uma solicitação, por
            exemplo, por obrigação legal, preservação de direitos ou impossibilidade técnica
            legítima.
          </p>
          <p>
            Você também pode consultar materiais públicos da{" "}
            <ExternalPolicyLink href="https://www.gov.br/anpd/pt-br">
              Autoridade Nacional de Proteção de Dados
            </ExternalPolicyLink>
            .
          </p>
        </PolicySection>

        <PolicySection id="seguranca" eyebrow="8" title="Como mantemos seus dados seguros">
          <p>
            Adotamos medidas técnicas, administrativas e organizacionais proporcionais ao risco do
            tratamento, com o objetivo de proteger dados pessoais contra acessos não autorizados,
            perda, alteração, divulgação indevida ou destruição.
          </p>
          <p>Essas medidas podem incluir:</p>
          <PolicyList items={securityItems} />
          <p>
            Nenhum sistema é absolutamente seguro. Se ocorrer incidente de segurança que possa gerar
            risco ou dano relevante aos titulares, avaliaremos o caso e adotaremos as medidas
            cabíveis, incluindo comunicação aos titulares e à ANPD quando exigido pela legislação.
          </p>
        </PolicySection>

        <PolicySection id="criancas-adolescentes" eyebrow="9" title="Crianças e adolescentes">
          <p>
            O Parserly é voltado a pessoas que buscam análise de currículo e desenvolvimento
            profissional. Não direcionamos o serviço a crianças.
          </p>
          <p>
            Se houver tratamento de dados de adolescentes ou menores de idade, ele deverá observar a
            LGPD e o melhor interesse da criança ou adolescente, com participação dos responsáveis
            legais quando exigido. Caso você identifique envio indevido de dados de criança ou
            adolescente, entre em contato pelo canal <PolicyValue>{PRIVACY_CONTACT}</PolicyValue>.
          </p>
        </PolicySection>

        <PolicySection id="decisoes-automatizadas" eyebrow="10" title="Decisões automatizadas e uso de IA">
          <p>
            Usamos tecnologia de IA para apoiar a leitura do currículo e gerar pontuações,
            diagnósticos e recomendações. O resultado da análise tem finalidade informativa e de
            apoio ao usuário, não substitui avaliação humana de recrutadores e não garante
            contratação, entrevista ou aprovação em processo seletivo.
          </p>
          <p>
            Quando houver decisão tomada unicamente com base em tratamento automatizado que produza
            efeitos relevantes sobre você, você poderá solicitar revisão e informações sobre
            critérios e procedimentos utilizados, observados os segredos comercial e industrial e os
            limites legais aplicáveis.
          </p>
        </PolicySection>

        <PolicySection id="alteracoes" eyebrow="11" title="Alterações nesta Política">
          <p>
            Podemos atualizar esta Política para refletir mudanças no serviço, na lei, em orientações
            da ANPD, em fornecedores ou em nossas práticas de tratamento de dados.
          </p>
          <p>
            Quando a alteração for relevante, adotaremos meios razoáveis para informar você, como
            aviso no site, e-mail ou destaque na própria página. A data de atualização no início do
            documento indicará a versão mais recente.
          </p>
        </PolicySection>

        <PolicySection
          id="contato-dpo"
          eyebrow="12"
          title="Contato de privacidade e LGPD"
        >
          <PolicyTable headers={["Campo", "Informação"]} rows={contactRows} />
          <p>
            Este é o canal adequado para dúvidas sobre privacidade, solicitações de direitos LGPD,
            revogação de consentimento, oposição ao tratamento e demais assuntos relacionados ao uso
            de dados pessoais pelo Parserly.
          </p>
        </PolicySection>
      </div>
    </main>
  );
}

function PolicySection({
  id,
  eyebrow,
  title,
  children
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="border-t border-line/55 py-8">
      <div className="grid min-w-0 gap-5 lg:grid-cols-[14rem_1fr]">
        <SectionHeading eyebrow={eyebrow} title={title} id={`${id}-title`} />
        <div className="min-w-0 space-y-5 text-sm leading-7 text-paper/70">{children}</div>
      </div>
    </section>
  );
}

function SectionHeading({
  eyebrow,
  title,
  id
}: {
  eyebrow: string;
  title: string;
  id: string;
}) {
  return (
    <div>
      <p className="text-xs font-bold uppercase text-acid">{eyebrow}</p>
      <h2 id={id} className="mt-2 font-display text-2xl font-semibold leading-tight text-paper">
        {title}
      </h2>
    </div>
  );
}

function Subsection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="min-w-0 space-y-4 rounded-md border border-line/70 bg-graphite/65 p-4">
      <h3 className="font-display text-xl font-semibold text-paper">{title}</h3>
      <div className="space-y-4">{children}</div>
    </section>
  );
}

function PolicyList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item} className="flex gap-3">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-acid" aria-hidden="true" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function PolicyTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <>
      <div className="space-y-3 md:hidden">
        {rows.map((row) => (
          <article key={row.join("|")} className="rounded-md border border-line/70 bg-graphite/80 p-4 shadow-tool">
            {row.map((cell, index) => (
              <div key={`${row[0]}-${headers[index]}`} className={index > 0 ? "mt-4 border-t border-line/55 pt-4" : ""}>
                <p className="text-xs font-bold uppercase text-paper/45">{headers[index]}</p>
                <p className={index === 0 ? "mt-1 font-semibold text-paper" : "mt-1 leading-6 text-paper/70"}>
                  {cell}
                </p>
              </div>
            ))}
          </article>
        ))}
      </div>

      <div className="hidden min-w-0 max-w-full overflow-x-auto rounded-md border border-line/70 bg-graphite/80 shadow-tool md:block">
        <table className="w-max min-w-full border-collapse text-left text-sm">
          <thead className="bg-night/70 text-xs uppercase text-paper/55">
            <tr>
              {headers.map((header) => (
                <th key={header} scope="col" className="border-b border-line/70 px-4 py-3 font-bold">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line/55 text-paper/70">
            {rows.map((row) => (
              <tr key={row.join("|")} className="align-top">
                {row.map((cell, index) => (
                  <td key={`${row[0]}-${index}`} className="min-w-[12rem] px-4 py-4 leading-6">
                    {index === 0 ? <span className="font-semibold text-paper">{cell}</span> : cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function PolicyValue({ children }: { children: ReactNode }) {
  return <span className="font-mono text-acid">{children}</span>;
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-amber/35 bg-amber/10 px-4 py-3 text-sm leading-6 text-paper/78">
      {children}
    </div>
  );
}

function ExternalPolicyLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="focus-ring inline-flex items-center gap-1 rounded-sm text-acid underline decoration-acid/50 underline-offset-4"
    >
      {children}
      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
    </a>
  );
}
