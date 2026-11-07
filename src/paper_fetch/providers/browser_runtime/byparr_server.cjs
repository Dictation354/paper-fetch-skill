// Use the exact Node/Playwright installation used by both Python controllers.
const fs = require('fs');
const settings = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const { firefox } = require(settings.playwright_package);
(async () => {
  const server = await firefox.launchServer({
    ...settings.launch_options,
    host: '127.0.0.1',
    _sharedBrowser: true,
    ...(settings.user_data_dir ? {_userDataDir: settings.user_data_dir, acceptDownloads: "accept"} : {}),
  });
  const path = settings.work_dir + '/browser.json';
  fs.writeFileSync(path + '.tmp', JSON.stringify({endpoint: server.wsEndpoint()}));
  fs.renameSync(path + '.tmp', path);
  process.stdin.on('data', data => {
    if (data.toString().trim() === 'close') server.close().finally(() => process.exit(0));
  });
  process.on('SIGTERM', () => server.close().finally(() => process.exit(0)));
  process.on('SIGINT', () => server.close().finally(() => process.exit(0)));
  server.on('close', () => process.exit(0));
})().catch(error => { console.error(error); process.exit(1); });
