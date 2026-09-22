from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, (label, count)
    return text.replace(old, new, 1)


# Previously validated selector corrections: review 4069005171, 4069005181, 4069005197.
p = Path('javascript/lib/node/tests/proxy-settings.spec.ts')
s = p.read_text()
s = replace_once(s, "['example.org', 'https://sub.example.org', false]", "['example.org', 'https://sub.example.org', true]", 'dns suffix expected result')
old = "      ['[::1]', 'http://[::1]', true],"
s = replace_once(s, old, old + "\n      ['::1', 'http://[::1]', true],\n      ['http://example.org', 'http://example.org', false],", 'ipv6/url rows')
p.write_text(s)

p = Path('javascript/lib/node/src/proxy-settings.ts')
s = p.read_text()
s = replace_once(s, "const { UrlWithStringQuery, parse } = require('url');", "const { UrlWithStringQuery, parse } = require('url');\nconst { isIP } = require('net');", 'isIP import')
s = replace_once(s, '  private readonly noProxy: string;', '  private readonly noProxy: { host: string; suffix: string; port?: number }[] = [];', 'parsed noProxy field')
old = "    this.noProxy = options?.url !== undefined || options?.ignoreProxyFromEnv\n      ? '' : process.env.no_proxy || process.env.NO_PROXY || '';"
new = """    const noProxy = options?.url !== undefined || options?.ignoreProxyFromEnv
      ? '' : process.env.no_proxy || process.env.NO_PROXY || '';
    for (const entry of noProxy.toLowerCase().split(/[\\s,]+/)) {
      const normalizedEntry = isIP(entry) === 6 ? `[${entry}]` : entry;
      const match = /^(\\[[^\\]]+\\]|[^:]+)(?::(\\d+))?$/.exec(normalizedEntry);
      if (match === null) {
        continue;
      }
      const host = match[1].replace(/^\\*\\./, '.').replace(/\\.$/, '');
      const suffix = host.startsWith('.') ? host : isIP(host.replace(/^\\[|\\]$/g, '')) === 0 ? `.${host}` : '';
      this.noProxy.push({ host, suffix, port: match[2] === undefined ? undefined : Number(match[2]) });
    }"""
s = replace_once(s, old, new, 'parse noProxy once')
old = """    return this.noProxy.toLowerCase().split(/[\\s,]+/).some(entry => {
      if (entry === '*') {
        return true;
      }
      const match = /^(\\[[^\\]]+\\]|[^:]+)(?::(\\d+))?$/.exec(entry);
      if (match === null || (match[2] !== undefined && Number(match[2]) !== Number(port))) {
        return false;
      }
      const host = match[1].replace(/^\\*\\./, '.').replace(/\\.$/, '');
      return host.startsWith('.') ? hostname.endsWith(host) : hostname === host;
    });"""
new = """    return this.noProxy.some(entry =>
      (entry.host === '*' && entry.port === undefined)
      || ((entry.port === undefined || entry.port === Number(port))
        && (hostname === entry.host || (entry.suffix !== '' && hostname.endsWith(entry.suffix)))));"""
s = replace_once(s, old, new, 'preparsed matcher')
p.write_text(s)

# Review 4069005230: document protocol-specific environment variables.
p = Path('javascript/lib/node/README.md')
s = p.read_text()
s = replace_once(
    s,
    "Currently, it supports either reading directly from 'https_proxy' (or 'HTTPS_PROXY') environment variable\nor manually setting the proxy settings.",
    "HTTP/WS connections read `http_proxy` (or `HTTP_PROXY`); HTTPS/WSS connections read\n`https_proxy` (or `HTTPS_PROXY`). Proxy settings may also be supplied manually.",
    'proxy env docs',
)
s = replace_once(
    s,
    "Entries may be separated by commas or whitespace and are case-insensitive; a trailing DNS root dot is ignored. A bare hostname or IP\nmatches exactly; `.example.org` or `*.example.org` matches subdomains only (add `example.org` separately\nto exclude the domain itself). An optional `:port` limits the match to that port; omitted URL ports\nuse 80 for HTTP/WS and 443 for HTTPS/WSS. IPv6 entries use brackets, e.g. `[::1]:8080`. `*` excludes all",
    "Entries may be separated by commas or whitespace and are case-insensitive; a trailing DNS root dot is ignored.\nA bare hostname matches itself and its subdomains; an IP address matches exactly.\n`.example.org` or `*.example.org` matches subdomains only. An optional `:port` limits the match to that port; omitted URL ports\nuse 80 for HTTP/WS and 443 for HTTPS/WSS. IPv6 entries may be bare (`::1`) or bracketed; use brackets with a port,\ne.g. `[::1]:8080`. `*` excludes all",
    'no_proxy docs',
)
p.write_text(s)

# Review 4069005216: never replace Node's special process.env object.
p = Path('javascript/lib/node/tests/proxy-settings.spec.ts')
s = p.read_text()
old = """const PROXY_URL = 'http://localhost:3128';

describe('ProxyAgent', () => {
  let savedEnvironment: NodeJS.ProcessEnv;

  beforeEach(() => {
    savedEnvironment = { ...process.env };
    ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'NO_PROXY', 'no_proxy']
      .forEach(name => delete process.env[name]);
  });

  afterEach(() => {
    process.env = savedEnvironment;
  });"""
new = """const PROXY_URL = 'http://localhost:3128';
const PROXY_ENVIRONMENT_KEYS = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'NO_PROXY', 'no_proxy'] as const;

describe('ProxyAgent', () => {
  let savedEnvironment: Map<string, string | undefined>;

  beforeEach(() => {
    savedEnvironment = new Map(PROXY_ENVIRONMENT_KEYS.map(name => [name, process.env[name]]));
    PROXY_ENVIRONMENT_KEYS.forEach(name => delete process.env[name]);
  });

  afterEach(() => {
    PROXY_ENVIRONMENT_KEYS.forEach(name => {
      const value = savedEnvironment.get(name);
      if (value === undefined) {
        delete process.env[name];
      } else {
        process.env[name] = value;
      }
    });
  });"""
s = replace_once(s, old, new, 'proxy settings env restore')
p.write_text(s)

# HTTP test environment restoration + responder-side assertion diagnostics (4069005216, 4069005220).
p = Path('javascript/lib/node/tests/node-http.spec.ts')
s = p.read_text()
old = """describe('NodeHttp', () => {

  afterAll(nock.restore);

  afterEach(nock.cleanAll);

  beforeEach(() => {
    delete process.env.HTTPS_PROXY;
    delete process.env.https_proxy;
    delete process.env.HTTP_PROXY;
    delete process.env.http_proxy;
    delete process.env.NO_PROXY;
    delete process.env.no_proxy;
  });"""
new = """describe('NodeHttp', () => {
  const proxyEnvironmentKeys = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'NO_PROXY', 'no_proxy'] as const;
  let savedEnvironment: Map<string, string | undefined>;

  afterAll(nock.restore);

  afterEach(() => {
    nock.cleanAll();
    proxyEnvironmentKeys.forEach(name => {
      const value = savedEnvironment.get(name);
      if (value === undefined) {
        delete process.env[name];
      } else {
        process.env[name] = value;
      }
    });
  });

  beforeEach(() => {
    savedEnvironment = new Map(proxyEnvironmentKeys.map(name => [name, process.env[name]]));
    proxyEnvironmentKeys.forEach(name => delete process.env[name]);
  });"""
s = replace_once(s, old, new, 'http env restore')
old = """    const proxyAgent = new ProxyAgent({ username: 'synthetic-user', password: 'synthetic-password' });
    nock(`${protocol}://localhost:8080`)
      .get('/get')
      .reply(200, function () {
        expect(this.req.getHeader('proxy-authorization')).toBeUndefined();
        return { proxied: Boolean((this.req as any).options.agent) };
      });
    const response = await new NodeRequester(proxyAgent)
      .doRequest(HttpVerb.GET, `${protocol}://localhost:8080/get`, new Map(), '');
    expect(response.body).toEqual({ proxied: false });"""
new = """    const proxyAgent = new ProxyAgent({ username: 'synthetic-user', password: 'synthetic-password' });
    let proxyAuthorization: unknown = 'unset';
    nock(`${protocol}://localhost:8080`)
      .get('/get')
      .reply(200, function () {
        proxyAuthorization = this.req.getHeader('proxy-authorization');
        return { proxied: Boolean((this.req as any).options.agent) };
      });
    const response = await new NodeRequester(proxyAgent)
      .doRequest(HttpVerb.GET, `${protocol}://localhost:8080/get`, new Map(), '');
    expect(response.body).toEqual({ proxied: false });
    expect(proxyAuthorization).toBeUndefined();"""
s = replace_once(s, old, new, 'nock assertion location')
s = replace_once(s, "    const savedEnvironment = { ...process.env };\n    let proxyRequests = 0;", "    let proxyRequests = 0;\n    let destinationProxyAuthorization: string | string[] | undefined;", 'remove local env replacement')
s = replace_once(
    s,
    """    const destination = http.createServer((req, res) => {
      expect(req.headers['proxy-authorization']).toBeUndefined();
      res.end(JSON.stringify({ direct: true }));
    });""",
    """    const destination = http.createServer((req, res) => {
      destinationProxyAuthorization = req.headers['proxy-authorization'];
      res.end(JSON.stringify({ direct: true }));
    });""",
    'destination assertion capture',
)
s = replace_once(
    s,
    """      expect(response.body).toEqual({ direct: true });
      expect(proxyRequests).toBe(0);""",
    """      expect(response.body).toEqual({ direct: true });
      expect(destinationProxyAuthorization).toBeUndefined();
      expect(proxyRequests).toBe(0);""",
    'destination assertion body',
)
s = replace_once(
    s,
    """    } finally {
      process.env = savedEnvironment;
      await Promise.all([destination, proxy].map(server => new Promise<void>(resolve => server.close(() => resolve()))));
    }""",
    """    } finally {
      await Promise.all([destination, proxy].map(server => new Promise<void>(resolve => server.close(() => resolve()))));
    }""",
    'remove http env object replacement',
)
p.write_text(s)

# WebSocket helper naming/authenticated destination (4069005204 part 2, 4069005210).
p = Path('javascript/lib/node/src/node-websocket.ts')
s = p.read_text()
s = replace_once(s, '        agent: NodeWebSocket.getProxyAgentForProtocol(url, agent),', '        agent: NodeWebSocket.resolveAgentForDestination(authenticatedUrl, agent),', 'authenticated proxy destination')
s = replace_once(s, '  private static getProxyAgentForProtocol(url: DittoURL, agent: ProxyAgent): http.Agent | undefined {', '  private static resolveAgentForDestination(url: DittoURL, agent: ProxyAgent): http.Agent | undefined {', 'websocket helper name')
p.write_text(s)

# WebSocket test env restoration and diagnosable listening failure (4069005216, 4069005226 partial).
p = Path('javascript/lib/node/tests/node-websocket.spec.ts')
s = p.read_text()
marker = """const noopHandler: any = {
  handleInput: () => { /* noop */ },
  handleResponse: () => { /* noop */ },
  handleMessage: () => { /* noop */ },
  handleClose: (promise: Promise<unknown>) => { promise.catch(() => { /* reconnect disabled in test */ }); },
  handleFailure: () => { /* noop */ },
  handleError: () => { /* noop */ }
};"""
replacement = marker + """

const proxyEnvironmentKeys = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'NO_PROXY', 'no_proxy'] as const;
const saveProxyEnvironment = (): Map<string, string | undefined> =>
  new Map(proxyEnvironmentKeys.map(name => [name, process.env[name]]));
const restoreProxyEnvironment = (saved: Map<string, string | undefined>): void => {
  proxyEnvironmentKeys.forEach(name => {
    const value = saved.get(name);
    if (value === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
  });
};"""
s = replace_once(s, marker, replacement, 'websocket env helpers')
s = replace_once(
    s,
    "    const savedEnvironment = { ...process.env };\n    const server = new WebSocket.Server({ port: 0, host: '127.0.0.1' });\n    await new Promise<void>(resolve => server.once('listening', resolve));",
    """    const savedEnvironment = saveProxyEnvironment();
    const server = new WebSocket.Server({ port: 0, host: '127.0.0.1' });
    await new Promise<void>((resolve, reject) => {
      const onError = (error: Error) => reject(error);
      server.once('error', onError);
      server.once('listening', () => {
        server.removeListener('error', onError);
        resolve();
      });
    });""",
    'ws server error path',
)
s = replace_once(
    s,
    """      const client = await NodeWebSocket.buildInstance(url, noopHandler, [], new ProxyAgent(), false);
      client.close();""",
    """      const client = await NodeWebSocket.buildInstance(url, noopHandler, [], new ProxyAgent(), false);
      expect(client).toBeTruthy();
      client.close();""",
    'ws explicit assertion',
)
s = replace_once(s, '      process.env = savedEnvironment;\n      server.clients.forEach(client => client.terminate());', '      restoreProxyEnvironment(savedEnvironment);\n      server.clients.forEach(client => client.terminate());', 'ws env restore first test')
s = replace_once(s, "    const savedEnvironment = { ...process.env };\n    try {\n      process.env.HTTPS_PROXY = 'http://127.0.0.1:1';", "    const savedEnvironment = saveProxyEnvironment();\n    try {\n      process.env.HTTPS_PROXY = 'http://127.0.0.1:1';", 'wss save env')
s = replace_once(s, '    } finally {\n      process.env = savedEnvironment;\n    }', '    } finally {\n      restoreProxyEnvironment(savedEnvironment);\n    }', 'wss restore env')
p.write_text(s)
