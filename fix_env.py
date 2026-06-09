content = open('.env', 'r').read()

start = content.find('-----BEGIN RSA PRIVATE KEY-----')
end = content.find('-----END RSA PRIVATE KEY-----') + len('-----END RSA PRIVATE KEY-----')
pem = content[start:end]

pem_single = pem.replace('\r\n', '\n').replace('\n', '\\n')

key_start = content.rfind('KALSHI_PRIVATE_KEY=', 0, start)
old_block = content[key_start:end]
new_block = 'KALSHI_PRIVATE_KEY="' + pem_single + '"'

fixed = content.replace(old_block, new_block)
open('.env', 'w').write(fixed)
print('Done. KALSHI_PRIVATE_KEY line (truncated):')
for line in fixed.splitlines():
    if line.startswith('KALSHI_PRIVATE_KEY'):
        print(line[:100] + '...')
        break
