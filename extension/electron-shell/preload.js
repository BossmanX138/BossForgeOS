const { contextBridge } = require('electron');

const backendHost = process.env.BOSSFORGE_HOST || '127.0.0.1';
const backendPort = Number(process.env.BOSSFORGE_PORT || 5005);

contextBridge.exposeInMainWorld('bossforgeShell', {
  backend: {
    host: backendHost,
    port: backendPort,
    url: `http://${backendHost}:${backendPort}`,
  },
  shell: {
    platform: process.platform,
    versions: {
      electron: process.versions.electron,
      chrome: process.versions.chrome,
      node: process.versions.node,
    },
  },
});
