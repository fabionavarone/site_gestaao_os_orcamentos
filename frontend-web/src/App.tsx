import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { api, login, User } from './api';
import { Bot, Conversation, ConversationOptions, Customer, Detail, Equipment, InboxEvent, Outbox, SelectOption, ServiceOrder } from './types';
import Workflows from './Workflows';

const loginSchema = z.object({
  email: z.string().email('E-mail inválido'),
  password: z.string().min(12, 'Use ao menos 12 caracteres'),
});
const noConversationOptions: ConversationOptions = { users: [], teams: [], customers: [], equipment: [], service_orders: [] };

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) });
  const [error, setError] = useState('');
  return <main className="grid min-h-screen place-items-center p-4">
    <form aria-label="Entrar" className="card w-full max-w-sm space-y-4" onSubmit={handleSubmit(async values => {
      setError('');
      try { onLogin(await login(values.email, values.password)); }
      catch (reason) { setError((reason as Error).message); }
    })}>
      <div><p className="text-xs font-bold uppercase tracking-[.2em] text-brand">Provisão</p><h1 className="text-2xl font-semibold">Central de atendimento</h1></div>
      <label className="block">E-mail<input className="mt-1 w-full" autoComplete="username" {...register('email')} /></label>
      {errors.email && <p role="alert" className="text-red-700">{errors.email.message}</p>}
      <label className="block">Senha<input className="mt-1 w-full" type="password" autoComplete="current-password" {...register('password')} /></label>
      {errors.password && <p role="alert" className="text-red-700">{errors.password.message}</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      <button className="w-full" disabled={isSubmitting}>{isSubmitting ? 'Entrando…' : 'Entrar'}</button>
    </form>
  </main>;
}

function OptionSelect({ label, value, options, onChange }: { label: string; value: string; options: SelectOption[]; onChange: (value: string) => void }) {
  return <select aria-label={label} value={value} onChange={event => onChange(event.target.value)}><option value="">Nenhum</option>{options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select>;
}

function ConversationActions({ conversation, options, refresh }: { conversation: Detail; options: ConversationOptions; refresh: () => void }) {
  const [assignee, setAssignee] = useState(conversation.assigned_to || '');
  const [team, setTeam] = useState(conversation.assigned_team_id || '');
  const [customer, setCustomer] = useState(conversation.customer_id || '');
  const [equipment, setEquipment] = useState(conversation.equipment_id || '');
  const [serviceOrder, setServiceOrder] = useState(conversation.service_order_id || '');
  const mutation = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => api(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
    onSuccess: refresh,
  });
  const changeState = (status: string) => mutation.mutate({ path: `/conversations/${conversation.id}/state`, body: {
    status,
    assigned_user_id: status === 'assigned' ? assignee || undefined : undefined,
    assigned_team_id: team || undefined,
  } });
  return <div className="mt-3 space-y-3 border-t pt-3">
    <div className="flex flex-wrap gap-2" aria-label="Ações da conversa">
      <button onClick={() => changeState('assigned')}>Assumir</button>
      <button onClick={() => changeState('queued')}>Devolver à fila</button>
      <button onClick={() => changeState('waiting_customer')}>Aguardar cliente</button>
      <button onClick={() => changeState('waiting_internal')}>Aguardar equipe</button>
      <button onClick={() => changeState('resolved')}>Resolver</button>
      <button onClick={() => changeState(conversation.status === 'closed' ? 'queued' : 'closed')}>{conversation.status === 'closed' ? 'Reabrir' : 'Fechar'}</button>
      <button className="bg-slate-600" onClick={() => mutation.mutate({ path: `/conversations/${conversation.id}/automation/${conversation.automation_paused ? 'resume' : 'pause'}` })}>{conversation.automation_paused ? 'Retomar automação' : 'Pausar automação'}</button>
    </div>
    <div className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
      <OptionSelect label="Atendente" value={assignee} options={options.users} onChange={setAssignee} />
      <OptionSelect label="Equipe" value={team} options={options.teams} onChange={setTeam} />
      <button onClick={() => changeState('assigned')}>Transferir</button>
    </div>
    <div className="grid gap-2 md:grid-cols-[1fr_1fr_1fr_auto]">
      <OptionSelect label="Cliente" value={customer} options={options.customers} onChange={setCustomer} />
      <OptionSelect label="Equipamento" value={equipment} options={options.equipment} onChange={setEquipment} />
      <OptionSelect label="Ordem de serviço" value={serviceOrder} options={options.service_orders} onChange={setServiceOrder} />
      <button onClick={() => mutation.mutate({ path: `/conversations/${conversation.id}/links`, body: {
        customer_id: customer || null,
        equipment_id: equipment || null,
        service_order_id: serviceOrder || null,
      } })}>Vincular</button>
    </div>
    {mutation.error && <p role="alert" className="text-red-700">{(mutation.error as Error).message}</p>}
  </div>;
}

function Inbox() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string>();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [channel, setChannel] = useState('');
  const [priority, setPriority] = useState('');
  const [bot, setBot] = useState('');
  const [team, setTeam] = useState('');
  const [assignee, setAssignee] = useState('');
  const [page, setPage] = useState(1);
  const [file, setFile] = useState<File>();
  const [text, setText] = useState('');
  const params = new URLSearchParams({ q: query, status_filter: status, channel, priority, bot_id: bot, team_id: team, assigned_to: assignee, page: String(page) });
  const list = useQuery({ queryKey: ['inbox', query, status, channel, priority, bot, team, assignee, page], queryFn: () => api<{ items: Conversation[] }>(`/conversations?${params}`), refetchInterval: 5000 });
  const detail = useQuery({ queryKey: ['conversation', selected], queryFn: () => api<Detail>(`/conversations/${selected}`), enabled: Boolean(selected) });
  const options = useQuery({ queryKey: ['conversation-options'], queryFn: () => api<ConversationOptions>('/conversation-options') });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['inbox'] });
    queryClient.invalidateQueries({ queryKey: ['conversation', selected] });
  };
  const send = useMutation({ mutationFn: (internal: boolean) => api(`/conversations/${selected}/messages`, { method: 'POST', body: JSON.stringify({ body: text, internal }) }), onSuccess: () => { setText(''); refresh(); } });
  const upload = useMutation({ mutationFn: () => {
    const form = new FormData(); form.append('file', file!); if (text) form.append('caption', text);
    return api(`/conversations/${selected}/attachments`, { method: 'POST', body: form });
  }, onSuccess: () => { setFile(undefined); setText(''); refresh(); } });
  return <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
    <section className="card">
      <h2 className="text-xl font-semibold">Inbox</h2>
      <div className="my-3 grid grid-cols-2 gap-2">
        <input aria-label="Buscar" placeholder="Buscar conversa" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} />
        <select aria-label="Estado" value={status} onChange={event => setStatus(event.target.value)}><option value="">Todos os estados</option><option value="queued">Na fila</option><option value="assigned">Atribuídas</option><option value="waiting_customer">Aguardando cliente</option><option value="waiting_internal">Aguardando equipe</option><option value="resolved">Resolvidas</option><option value="closed">Fechadas</option></select>
        <select aria-label="Canal" value={channel} onChange={event => setChannel(event.target.value)}><option value="">Todos os canais</option><option value="telegram">Telegram</option><option value="web">Web</option></select>
        <select aria-label="Prioridade" value={priority} onChange={event => setPriority(event.target.value)}><option value="">Todas prioridades</option><option value="low">Baixa</option><option value="normal">Normal</option><option value="high">Alta</option><option value="urgent">Urgente</option></select>
        <input aria-label="Filtrar por bot" placeholder="ID do bot" value={bot} onChange={event => setBot(event.target.value)} />
        <input aria-label="Filtrar por equipe" placeholder="ID da equipe" value={team} onChange={event => setTeam(event.target.value)} />
        <input aria-label="Filtrar por responsável" placeholder="ID do responsável" value={assignee} onChange={event => setAssignee(event.target.value)} />
      </div>
      {list.isLoading && <p>Carregando…</p>}
      {list.error && <p role="alert">{(list.error as Error).message}</p>}
      <div className="space-y-2">{list.data?.items.map(conversation => <button key={conversation.id} onClick={() => setSelected(conversation.id)} className="w-full bg-white text-left text-ink hover:bg-slate-50"><span className="font-medium">{conversation.subject}</span><span className="float-right badge">{conversation.status}</span><span className="block muted">{conversation.channel} · {conversation.unread_count} não lidas</span></button>)}{list.data?.items.length === 0 && <p className="muted">Nenhuma conversa encontrada.</p>}</div>
      <div className="mt-3 flex justify-between"><button disabled={page === 1} onClick={() => setPage(value => value - 1)}>Anterior</button><span>Página {page}</span><button disabled={(list.data?.items.length || 0) < 50} onClick={() => setPage(value => value + 1)}>Próxima</button></div>
    </section>
    <section className="card min-h-[32rem]">
      {!selected ? <div className="grid h-full place-items-center muted">Selecione uma conversa</div> : detail.isLoading ? <p>Carregando histórico…</p> : detail.data ? <>
        <header className="border-b pb-3"><h2 className="text-xl font-semibold">{detail.data.subject}</h2><p className="muted">{detail.data.status} · {detail.data.channel} · {detail.data.automation_paused ? 'automação pausada' : 'automação ativa'}</p><ConversationActions key={`${detail.data.id}:${detail.data.updated_at || detail.data.status}`} conversation={detail.data} options={{ ...noConversationOptions, ...options.data }} refresh={refresh} /></header>
        <div aria-label="Histórico" className="my-4 max-h-[55vh] space-y-3 overflow-auto">{detail.data.messages.map(message => <article key={message.id} className={`max-w-[85%] rounded-xl p-3 ${message.internal ? 'mx-auto bg-amber-50' : message.direction === 'outbound' ? 'ml-auto bg-cyan-50' : 'bg-slate-100'}`}><p className="text-xs font-medium">{message.author_name} · {message.status}{message.attempts ? ` · ${message.attempts} tentativa(s)` : ''}</p><p className="whitespace-pre-wrap">{message.text}</p>{message.attachments.map(attachment => <a className="block" key={attachment.id} href={`/api/v1/attachments/${attachment.id}/download`}>{attachment.filename}</a>)}</article>)}</div>
        <div className="flex gap-2"><textarea aria-label="Mensagem" className="min-h-20 flex-1" value={text} onChange={event => setText(event.target.value)} placeholder="Digite uma resposta" /><div className="grid gap-2"><button disabled={!text || send.isPending} onClick={() => send.mutate(false)}>Responder</button><button disabled={!text || send.isPending} className="bg-slate-600" onClick={() => send.mutate(true)}>Nota interna</button></div></div>
        <div className="mt-2 flex items-center gap-2"><input aria-label="Selecionar anexo" type="file" onChange={event => setFile(event.target.files?.[0])} /><button disabled={!file || upload.isPending} onClick={() => upload.mutate()}>Enviar anexo</button></div>
        {(send.error || upload.error) && <p role="alert">{((send.error || upload.error) as Error).message}</p>}
      </> : <p role="alert">Não foi possível abrir a conversa.</p>}
    </section>
  </div>;
}

function BotOperations({ bot, refresh }: { bot: Bot; refresh: () => void }) {
  const [mode, setMode] = useState(bot.mode);
  const [details, setDetails] = useState('');
  const action = useMutation({ mutationFn: async ({ action, method = 'POST', body }: { action: string; method?: string; body?: unknown }) => {
    const suffix = action ? `/${action}` : '';
    const result = await api<unknown>(`/telegram/bots/${bot.id}${suffix}`, { method, body: body ? JSON.stringify(body) : undefined });
    if (action === 'health' || action === 'delivery-metrics') setDetails(JSON.stringify(result));
    return result;
  }, onSuccess: refresh });
  return <>
    <div className="mt-3 flex flex-wrap gap-2">
      <button onClick={() => action.mutate({ action: 'validate' })}>Validar</button>
      <button onClick={() => action.mutate({ action: bot.active ? 'deactivate' : 'activate' })}>{bot.active ? 'Desativar' : 'Ativar'}</button>
      <select aria-label={`Modo de ${bot.name}`} value={mode} disabled={bot.active} onChange={event => setMode(event.target.value)}><option value="webhook">Webhook</option><option value="polling">Polling</option><option value="disabled">Desativado</option></select>
      <button disabled={bot.active || mode === bot.mode} onClick={() => action.mutate({ action: '', method: 'PATCH', body: { mode } })}>Salvar modo</button>
      <button onClick={() => action.mutate({ action: 'configure-webhook' })}>Configurar webhook</button>
      <button onClick={() => action.mutate({ action: 'webhook', method: 'DELETE' })}>Remover webhook</button>
      <button onClick={() => action.mutate({ action: 'health', method: 'GET' })}>Saúde</button>
      <button onClick={() => action.mutate({ action: 'delivery-metrics', method: 'GET' })}>Métricas</button>
    </div>
    {details && <pre className="mt-2 overflow-auto rounded bg-slate-100 p-2 text-xs">{details}</pre>}
    {action.error && <p role="alert" className="text-red-700">{(action.error as Error).message}</p>}
  </>;
}

function Bots() {
  const queryClient = useQueryClient();
  const bots = useQuery({ queryKey: ['bots'], queryFn: () => api<{ items: Bot[] }>('/telegram/bots') });
  const [name, setName] = useState(''); const [token, setToken] = useState(''); const [mode, setMode] = useState('webhook'); const [replaceId, setReplaceId] = useState('');
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['bots'] });
  const create = useMutation({ mutationFn: () => api('/telegram/bots', { method: 'POST', body: JSON.stringify({ name, token, mode }) }), onSuccess: () => { setName(''); setToken(''); refresh(); } });
  const replace = useMutation({ mutationFn: () => api(`/telegram/bots/${replaceId}/replace-token`, { method: 'POST', body: JSON.stringify({ token }) }), onSuccess: () => { setToken(''); setReplaceId(''); refresh(); } });
  return <div className="space-y-4">
    <section className="card"><h2 className="text-xl font-semibold">{replaceId ? 'Substituir token' : 'Novo bot Telegram'}</h2><div className="mt-3 flex flex-wrap gap-2">{!replaceId && <input aria-label="Nome do bot" placeholder="Nome interno" value={name} onChange={event => setName(event.target.value)} />}<input aria-label="Token do bot" type="password" autoComplete="off" placeholder="Token" value={token} onChange={event => setToken(event.target.value)} />{!replaceId && <select aria-label="Modo" value={mode} onChange={event => setMode(event.target.value)}><option value="webhook">Webhook</option><option value="polling">Polling</option><option value="disabled">Desativado</option></select>}<button disabled={!token || (!replaceId && !name)} onClick={() => replaceId ? replace.mutate() : create.mutate()}>{replaceId ? 'Validar e substituir' : 'Validar e cadastrar'}</button>{replaceId && <button className="bg-slate-600" onClick={() => setReplaceId('')}>Cancelar</button>}</div>{(create.error || replace.error) && <p role="alert">{((create.error || replace.error) as Error).message}</p>}</section>
    <section className="grid gap-3 md:grid-cols-2">{bots.data?.items.map(bot => <article className="card" key={bot.id}><h3 className="font-semibold">{bot.name} <span className="badge">{bot.status}</span></h3><p className="muted">@{bot.username || 'sem username'} · {bot.mode}</p><p className="font-mono text-xs">{bot.token}</p>{bot.last_error && <p className="text-red-700">{bot.last_error}</p>}<BotOperations bot={bot} refresh={refresh} /><button className="mt-2 bg-slate-600" onClick={() => setReplaceId(bot.id)}>Trocar token</button></article>)}</section>
  </div>;
}

function Deliveries() {
  const queryClient = useQueryClient();
  const data = useQuery({ queryKey: ['outbox'], queryFn: () => api<{ items: Outbox[] }>('/outbox') });
  const inbox = useQuery({ queryKey: ['external-events'], queryFn: () => api<{ items: InboxEvent[] }>('/external-events') });
  const retry = useMutation({ mutationFn: (id: string) => api(`/outbox/${id}/reprocess`, { method: 'POST' }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['outbox'] }) });
  const retryInbox = useMutation({ mutationFn: (id: string) => api(`/external-events/${id}/reprocess`, { method: 'POST' }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['external-events'] }) });
  return <div className="space-y-4">
    <section className="card overflow-auto"><h2 className="text-xl font-semibold">Entregas e dead-letter</h2><table className="mt-3 w-full text-left"><thead><tr><th>Estado</th><th>Operação</th><th>Tentativas</th><th>Erro</th><th></th></tr></thead><tbody>{data.data?.items.map(item => <tr className="border-t" key={item.id}><td className="py-3"><span className="badge">{item.status}</span></td><td>{item.operation}</td><td>{item.attempts}</td><td>{item.last_error || '—'}</td><td>{['dead_letter', 'failed'].includes(item.status) && <button onClick={() => retry.mutate(item.id)}>Reprocessar</button>}</td></tr>)}</tbody></table></section>
    <section className="card overflow-auto"><h2 className="text-xl font-semibold">Eventos de entrada</h2><table className="mt-3 w-full text-left"><thead><tr><th>Update</th><th>Estado</th><th>Tentativas</th><th>Erro</th><th></th></tr></thead><tbody>{inbox.data?.items.map(item => <tr className="border-t" key={item.id}><td>{item.external_event_id}</td><td><span className="badge">{item.status}</span></td><td>{item.attempts}</td><td>{item.error || '—'}</td><td>{['dead_letter', 'retry'].includes(item.status) && <button onClick={() => retryInbox.mutate(item.id)}>Reprocessar entrada</button>}</td></tr>)}</tbody></table></section>
  </div>;
}

function Customers() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState(''); const [selected, setSelected] = useState<string>(); const [name, setName] = useState(''); const [document, setDocument] = useState(''); const [email, setEmail] = useState(''); const [phone, setPhone] = useState('');
  const customers = useQuery({ queryKey: ['crm-customers', query], queryFn: () => api<{ items: Customer[] }>(`/crm/customers?q=${encodeURIComponent(query)}`) });
  const detail = useQuery({ queryKey: ['crm-customer', selected], queryFn: () => api<Customer>(`/crm/customers/${selected}`), enabled: Boolean(selected) });
  const create = useMutation({ mutationFn: () => api('/crm/customers', { method: 'POST', body: JSON.stringify({ name, document: document || null, email: email || null, phone: phone || null }) }), onSuccess: () => { setName(''); setDocument(''); setEmail(''); setPhone(''); queryClient.invalidateQueries({ queryKey: ['crm-customers'] }); } });
  return <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
    <section className="card"><h2 className="text-xl font-semibold">Clientes</h2><input className="my-3 w-full" aria-label="Buscar cliente" placeholder="Nome, documento ou contato" value={query} onChange={event => setQuery(event.target.value)} /><div className="space-y-2">{customers.data?.items.map(customer => <button key={customer.id} className="w-full bg-white text-left" onClick={() => setSelected(customer.id)}><span className="font-medium">{customer.name}</span><span className="float-right badge">{customer.status}</span><span className="block muted">{customer.document || customer.email || 'sem documento'}</span></button>)}{customers.data?.items.length === 0 && <p className="muted">Nenhum cliente encontrado.</p>}</div></section>
    <section className="card space-y-3"><h2 className="text-xl font-semibold">Novo cliente</h2><div className="grid gap-2 md:grid-cols-2"><input aria-label="Nome do cliente" placeholder="Nome ou razão social" value={name} onChange={event => setName(event.target.value)} /><input aria-label="CPF ou CNPJ" placeholder="CPF/CNPJ" value={document} onChange={event => setDocument(event.target.value)} /><input aria-label="E-mail do cliente" placeholder="E-mail" value={email} onChange={event => setEmail(event.target.value)} /><input aria-label="Telefone do cliente" placeholder="Telefone" value={phone} onChange={event => setPhone(event.target.value)} /></div><button disabled={!name || create.isPending} onClick={() => create.mutate()}>Cadastrar cliente</button>{create.error && <p role="alert" className="text-red-700">{(create.error as Error).message}</p>}{detail.data && <div className="border-t pt-3"><h3 className="font-semibold">{detail.data.name}</h3><p className="muted">{detail.data.email || 'sem e-mail'} · {detail.data.phone || 'sem telefone'}</p><h4 className="mt-3 font-medium">Contatos ({detail.data.contacts?.length || 0})</h4>{detail.data.contacts?.map(contact => <p key={contact.id}>{contact.name} · {contact.email || contact.phone || 'sem contato'}</p>)}<h4 className="mt-3 font-medium">Endereços ({detail.data.addresses?.length || 0})</h4>{detail.data.addresses?.map(address => <p key={address.id}>{address.street}, {address.city}/{address.state}</p>)}</div>}</section>
  </div>;
}

function EquipmentPage() {
  const queryClient = useQueryClient(); const [query, setQuery] = useState(''); const [customerId, setCustomerId] = useState(''); const [category, setCategory] = useState(''); const [serial, setSerial] = useState('');
  const items = useQuery({ queryKey: ['equipment', query, customerId], queryFn: () => api<{ items: Equipment[] }>(`/equipment?q=${encodeURIComponent(query)}&customer_id=${encodeURIComponent(customerId)}`) });
  const customers = useQuery({ queryKey: ['crm-customers-options'], queryFn: () => api<{ items: Customer[] }>('/crm/customers?limit=100') });
  const create = useMutation({ mutationFn: () => api('/equipment', { method: 'POST', body: JSON.stringify({ customer_id: customerId, category: category || 'Não categorizado', serial_number: serial || null }) }), onSuccess: () => { setCategory(''); setSerial(''); queryClient.invalidateQueries({ queryKey: ['equipment'] }); } });
  return <div className="grid gap-4 lg:grid-cols-[22rem_1fr]"><section className="card"><h2 className="text-xl font-semibold">Equipamentos</h2><input className="my-2 w-full" aria-label="Buscar equipamento" placeholder="Categoria, serial ou código" value={query} onChange={event => setQuery(event.target.value)} /><select className="w-full" aria-label="Cliente do equipamento" value={customerId} onChange={event => setCustomerId(event.target.value)}><option value="">Todos os clientes</option>{customers.data?.items.map(customer => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select><div className="mt-3 space-y-2">{items.data?.items.map(item => <article className="rounded border p-2" key={item.id}><p className="font-medium">{item.category} · {item.model || 'modelo não informado'}</p><p className="muted">{item.serial_number || item.internal_code} · {item.status}</p></article>)}</div></section><section className="card space-y-3"><h2 className="text-xl font-semibold">Novo equipamento</h2><select aria-label="Cliente para cadastro" value={customerId} onChange={event => setCustomerId(event.target.value)}><option value="">Selecione o cliente</option>{customers.data?.items.map(customer => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select><input aria-label="Categoria do equipamento" placeholder="Categoria" value={category} onChange={event => setCategory(event.target.value)} /><input aria-label="Número de série" placeholder="Número de série" value={serial} onChange={event => setSerial(event.target.value)} /><button disabled={!customerId || create.isPending} onClick={() => create.mutate()}>Cadastrar equipamento</button>{create.error && <p role="alert" className="text-red-700">{(create.error as Error).message}</p>}</section></div>;
}

function ServiceOrders() {
  const queryClient = useQueryClient(); const [query, setQuery] = useState(''); const [selected, setSelected] = useState<string>(); const [status, setStatus] = useState('');
  const [summary, setSummary] = useState(''); const [measurement, setMeasurement] = useState(''); const [testName, setTestName] = useState(''); const [checklistTemplate, setChecklistTemplate] = useState('');
  const orders = useQuery({ queryKey: ['service-orders', query, status], queryFn: () => api<{ items: ServiceOrder[] }>(`/service-orders?q=${encodeURIComponent(query)}&status=${status}`) });
  const detail = useQuery({ queryKey: ['service-order', selected], queryFn: () => api<Record<string, any>>(`/service-orders/${selected}`), enabled: Boolean(selected) });
  const templates = useQuery({ queryKey: ['checklist-templates'], queryFn: () => api<{ items: any[] }>('/checklist-templates') });
  const mutation = useMutation({ mutationFn: ({ path, body }: { path: string; body: unknown }) => api(path, { method: 'POST', body: JSON.stringify(body) }), onSuccess: () => { detail.refetch(); queryClient.invalidateQueries({ queryKey: ['service-orders'] }); } });
  return <div className="grid gap-4 lg:grid-cols-[24rem_1fr]"><section className="card"><h2 className="text-xl font-semibold">Ordens de serviço</h2><div className="my-3 grid gap-2"><input aria-label="Buscar OS" placeholder="Título" value={query} onChange={event => setQuery(event.target.value)} /><select aria-label="Estado da OS" value={status} onChange={event => setStatus(event.target.value)}><option value="">Todos os estados</option><option value="draft">Rascunho</option><option value="received">Recebida</option><option value="triage">Triagem</option><option value="diagnosis">Diagnóstico</option><option value="closed">Encerrada</option></select></div><div className="space-y-2">{orders.data?.items.map(order => <button key={order.id} className="w-full bg-white text-left" onClick={() => setSelected(order.id)}><span className="font-medium">OS {order.number} · {order.title}</span><span className="float-right badge">{order.status}</span><span className="block muted">{order.priority} · {order.service_type}</span></button>)}</div></section><section className="card">{!selected ? <p className="muted">Selecione uma OS</p> : detail.isLoading ? <p>Carregando…</p> : detail.data ? <><h2 className="text-xl font-semibold">OS {detail.data.number} · {detail.data.title}</h2><p className="muted">{detail.data.status} · prioridade {detail.data.priority} · SLA {detail.data.sla_violated ? 'violado' : 'ativo'}</p><h3 className="mt-4 font-semibold">Triagem</h3>{detail.data.triage ? <p>{detail.data.triage.observations || 'Triagem registrada'} · risco elétrico: {detail.data.triage.electrical_risk ? 'sim' : 'não'}</p> : <p className="muted">Ainda não registrada</p>}<div className="mt-4 grid gap-2 border-t pt-3"><h3 className="font-semibold">Registros técnicos</h3><div className="flex gap-2"><input aria-label="Resumo do diagnóstico" placeholder="Resumo do diagnóstico" value={summary} onChange={event => setSummary(event.target.value)} /><button disabled={!summary} onClick={() => { mutation.mutate({ path: `/service-orders/${selected}/diagnoses`, body: { summary } }); setSummary(''); }}>Salvar diagnóstico</button></div><div className="flex gap-2"><input aria-label="Medição" placeholder="Parâmetro: valor" value={measurement} onChange={event => setMeasurement(event.target.value)} /><button disabled={!measurement} onClick={() => { const [parameter, value] = measurement.split(':').map(item => item.trim()); mutation.mutate({ path: `/service-orders/${selected}/measurements`, body: { parameter, value: value || parameter } }); setMeasurement(''); }}>Registrar medição</button></div><div className="flex gap-2"><input aria-label="Teste técnico" placeholder="Nome do teste" value={testName} onChange={event => setTestName(event.target.value)} /><button disabled={!testName} onClick={() => { mutation.mutate({ path: `/service-orders/${selected}/technical-tests`, body: { name: testName, status: 'inconclusive' } }); setTestName(''); }}>Registrar teste</button></div><div className="flex gap-2"><select aria-label="Checklist publicado" value={checklistTemplate} onChange={event => setChecklistTemplate(event.target.value)}><option value="">Checklist publicado</option>{templates.data?.items.filter(item => item.status === 'published').map(item => <option key={item.id} value={item.id}>{item.name} v{item.version}</option>)}</select><button disabled={!checklistTemplate} onClick={() => mutation.mutate({ path: `/service-orders/${selected}/checklists?template_id=${checklistTemplate}`, body: {} })}>Aplicar checklist</button></div></div><h3 className="mt-4 font-semibold">Diagnósticos</h3>{detail.data.diagnoses?.map((item: any) => <p key={item.id}>{item.summary} · v{item.version} · {item.status}{item.status === 'draft' && <button className="ml-2" onClick={() => mutation.mutate({ path: `/service-orders/${selected}/diagnoses/${item.id}/submit-review`, body: {} })}>Enviar revisão</button>}{item.status === 'under_review' && <button className="ml-2" onClick={() => mutation.mutate({ path: `/service-orders/${selected}/diagnoses/${item.id}/approve`, body: {} })}>Aprovar</button>}</p>)}<h3 className="mt-4 font-semibold">Tarefas</h3>{detail.data.tasks?.map((task: any) => <p key={task.id}>{task.title} · {task.status}</p>)}<h3 className="mt-4 font-semibold">Checklists</h3>{detail.data.checklists?.map((item: any) => <p key={item.id}>{item.status} · {item.items?.length || 0} itens</p>)}<h3 className="mt-4 font-semibold">Timeline</h3>{detail.data.timeline?.map((event: any) => <p key={event.id} className="border-b py-1"><span className="font-medium">{event.event_type}</span> · {event.detail}</p>)}</> : <p role="alert">Não foi possível abrir a OS.</p>}</section></div>;
}

function CompletionOperations() {
  const [orderId, setOrderId] = useState(''); const [mode, setMode] = useState('bench'); const [address, setAddress] = useState('');
  const orders = useQuery({ queryKey: ['completion-orders'], queryFn: () => api<{ items: ServiceOrder[] }>('/service-orders?limit=100') });
  const mutation = useMutation({ mutationFn: ({ path, body }: { path: string; body: unknown }) => api(path, { method: 'POST', body: JSON.stringify(body) }) });
  return <section className="card max-w-3xl space-y-4"><h2 className="text-xl font-semibold">Atendimento, entrega e garantia</h2><select aria-label="OS para operação" value={orderId} onChange={event => setOrderId(event.target.value)}><option value="">Selecione uma OS</option>{orders.data?.items.map(order => <option key={order.id} value={order.id}>OS {order.number} · {order.title}</option>)}</select><div className="flex flex-wrap gap-2"><select aria-label="Modo de atendimento" value={mode} onChange={event => setMode(event.target.value)}><option value="bench">Bancada</option><option value="remote">Remoto</option><option value="field">Campo</option></select><button disabled={!orderId} onClick={() => mutation.mutate({ path: `/service-orders/${orderId}/work-sessions`, body: { mode } })}>Iniciar sessão</button><button disabled={!orderId} onClick={() => mutation.mutate({ path: `/service-orders/${orderId}/complete`, body: {} })}>Concluir tecnicamente</button><button disabled={!orderId} onClick={() => mutation.mutate({ path: `/service-orders/${orderId}/delivery`, body: { mode: 'pickup' } })}>Registrar retirada</button></div><div className="flex gap-2"><input aria-label="Endereço da visita" placeholder="Endereço da visita" value={address} onChange={event => setAddress(event.target.value)} /><button disabled={!orderId || !address} onClick={() => mutation.mutate({ path: `/service-orders/${orderId}/visits`, body: { address, scheduled_start: new Date(Date.now() + 86400000).toISOString() } })}>Agendar visita</button></div>{mutation.error && <p role="alert" className="text-red-700">{(mutation.error as Error).message}</p>}{mutation.isSuccess && <p className="text-green-700">Operação registrada.</p>}</section>;
}

export default function App() {
  const [user, setUser] = useState<User>(); const [checking, setChecking] = useState(true); const [tab, setTab] = useState<'inbox' | 'bots' | 'deliveries' | 'workflows' | 'customers' | 'equipment' | 'orders' | 'completion'>('inbox');
  useEffect(() => { api<{ user: User }>('/auth/me').then(result => setUser(result.user)).catch(() => {}).finally(() => setChecking(false)); }, []);
  if (checking) return <main className="grid min-h-screen place-items-center">Carregando…</main>;
  if (!user) return <Login onLogin={setUser} />;
  return <div className="min-h-screen"><header className="border-b bg-white"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 p-4"><div><strong>Provisão Manager</strong><span className="ml-2 muted">{user.name}</span></div><nav aria-label="Principal" className="flex flex-wrap gap-2"><button onClick={() => setTab('inbox')}>Inbox</button><button onClick={() => setTab('customers')}>Clientes</button><button onClick={() => setTab('equipment')}>Equipamentos</button><button onClick={() => setTab('orders')}>OS</button><button onClick={() => setTab('completion')}>Atendimento</button><button onClick={() => setTab('bots')}>Bots</button><button onClick={() => setTab('deliveries')}>Entregas</button><button onClick={() => setTab('workflows')}>Workflows</button><button className="bg-slate-600" onClick={async () => { await api('/auth/logout', { method: 'POST' }); setUser(undefined); }}>Sair</button></nav></div></header><main className="mx-auto max-w-7xl p-4">{tab === 'inbox' ? <Inbox /> : tab === 'customers' ? <Customers /> : tab === 'equipment' ? <EquipmentPage /> : tab === 'orders' ? <ServiceOrders /> : tab === 'completion' ? <CompletionOperations /> : tab === 'bots' ? <Bots /> : tab === 'deliveries' ? <Deliveries /> : <Workflows />}</main></div>;
}
