from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, (label, count)
    return text.replace(old, new, 1)


# Complete review 4069005204 without routing DittoURL through WHATWG URL parsing.
p = Path('javascript/lib/node/src/proxy-settings.ts')
s = p.read_text()
pattern = re.compile(
    r"  /\*\* Selects a proxy per destination, respecting exclusions for environment-configured proxies\. \*/\n"
    r"  public getAgentForUrl\(url: URL\): typeof HttpsProxyAgent \| undefined \{.*?\n"
    r"  private isExcluded\(url: URL\): boolean \{.*?\n  \}\n",
    re.S,
)
replacement = '''  /** Selects a proxy per destination, respecting exclusions for environment-configured proxies. */
  public getAgentForUrl(url: URL): typeof HttpsProxyAgent | undefined {
    return this.getAgentForDestinationParts(url.protocol, url.hostname, url.port);
  }

  /** Selects a proxy from already-separated Ditto URL parts without reparsing the destination. */
  public getAgentForDestination(protocol: string, domain: string): typeof HttpsProxyAgent | undefined {
    let hostname = domain.toLowerCase().replace(/\\.$/, '');
    let port = '';
    if (isIP(hostname) === 6) {
      hostname = `[${hostname}]`;
    } else {
      const bracketed = /^(\\[[^\\]]+\\])(?::(\\d+))?$/.exec(hostname);
      if (bracketed !== null) {
        hostname = bracketed[1];
        port = bracketed[2] || '';
      } else {
        const hostAndPort = /^(.*?)(?::(\\d+))?$/.exec(hostname);
        if (hostAndPort !== null) {
          hostname = hostAndPort[1];
          port = hostAndPort[2] || '';
        }
      }
    }
    return this.getAgentForDestinationParts(protocol, hostname, port);
  }

  private getAgentForDestinationParts(protocol: string, hostname: string, port: string): typeof HttpsProxyAgent | undefined {
    const normalizedProtocol = protocol.endsWith(':') ? protocol : `${protocol}:`;
    const normalizedHostname = hostname.toLowerCase().replace(/\\.$/, '');
    if (this.isExcluded(normalizedProtocol, normalizedHostname, port)) {
      return undefined;
    }
    return normalizedProtocol === 'https:' || normalizedProtocol === 'wss:' ? this.proxyAgent : this.httpProxyAgent;
  }

  private isExcluded(protocol: string, hostname: string, explicitPort: string): boolean {
    const port = explicitPort || (protocol === 'https:' || protocol === 'wss:' ? '443' : '80');
    return this.noProxy.some(entry =>
      (entry.host === '*' && entry.port === undefined)
      || ((entry.port === undefined || entry.port === Number(port))
        && (hostname === entry.host || (entry.suffix !== '' && hostname.endsWith(entry.suffix)))));
  }
'''
s, count = pattern.subn(replacement, s, count=1)
assert count == 1, ('destination methods', count)
p.write_text(s)

p = Path('javascript/lib/node/src/node-websocket.ts')
s = p.read_text()
s = replace_once(
    s,
    '    return agent.getAgentForUrl(new URL(url.toString()));',
    '    return agent.getAgentForDestination(url.protocol, url.domain);',
    'avoid websocket destination reparse',
)
p.write_text(s)

# Focused regression: the proxy selector must not introduce URL validation for a Ditto domain.
p = Path('javascript/lib/node/tests/proxy-settings.spec.ts')
s = p.read_text()
marker = '''    it('prefers nonempty lowercase no_proxy and evaluates each destination separately', () => {'''
test = '''    it('selects a proxy from Ditto URL parts without reparsing the domain', () => {
      const agent = new ProxyAgent();
      expect(() => agent.getAgentForDestination('ws', 'my host:8080')).not.toThrow();
      expect(agent.getAgentForDestination('ws', 'my host:8080')).toBe(agent.httpProxyAgent);
    });

'''
s = replace_once(s, marker, test + marker, 'Ditto domain no-reparse regression')
p.write_text(s)

# Complete review 4069005226 with a reachable fake proxy and an explicit zero-request assertion.
p = Path('javascript/lib/node/tests/node-websocket.spec.ts')
s = p.read_text()
s = replace_once(s, "import { IncomingMessage } from 'http';", "import * as http from 'http';", 'http namespace import')
s = replace_once(s, 'const acceptUpgrade = (req: IncomingMessage, socket: Socket): void => {', 'const acceptUpgrade = (req: http.IncomingMessage, socket: Socket): void => {', 'IncomingMessage type')
marker = '''});

/**
 * Regression tests for the TLS certificate validation of the NodeJS WebSocket transport.'''
new_test = '''
  it('does not contact a reachable proxy for an excluded ws destination', async () => {
    const savedEnvironment = saveProxyEnvironment();
    let proxyRequests = 0;
    const destination = new WebSocket.Server({ port: 0, host: '127.0.0.1' });
    const proxy = http.createServer((_req, res) => {
      proxyRequests++;
      res.writeHead(502);
      res.end();
    });
    const waitForListening = (server: WebSocket.Server | http.Server): Promise<void> => new Promise((resolve, reject) => {
      const onError = (error: Error) => reject(error);
      server.once('error', onError);
      server.once('listening', () => {
        server.removeListener('error', onError);
        resolve();
      });
    });
    proxy.listen(0, '127.0.0.1');
    await Promise.all([waitForListening(destination), waitForListening(proxy)]);
    try {
      const destinationPort = (destination.address() as AddressInfo).port;
      const proxyPort = (proxy.address() as AddressInfo).port;
      process.env.HTTP_PROXY = `http://127.0.0.1:${proxyPort}`;
      delete process.env.http_proxy;
      process.env.NO_PROXY = '127.0.0.1';
      delete process.env.no_proxy;
      const url = ImmutableURL.newInstance('ws', `127.0.0.1:${destinationPort}`, '/ws/2');
      const client = await NodeWebSocket.buildInstance(url, noopHandler, [], new ProxyAgent(), false);
      expect(client).toBeTruthy();
      expect(proxyRequests).toBe(0);
      client.close();
    } finally {
      restoreProxyEnvironment(savedEnvironment);
      destination.clients.forEach(client => client.terminate());
      await Promise.all([
        new Promise<void>(resolve => destination.close(() => resolve())),
        new Promise<void>(resolve => proxy.close(() => resolve()))
      ]);
    }
  });
});

/**
 * Regression tests for the TLS certificate validation of the NodeJS WebSocket transport.'''
s = replace_once(s, marker, new_test, 'reachable proxy counter regression')
p.write_text(s)
