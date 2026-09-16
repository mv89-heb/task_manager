import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'il.co.taskmanager.app',
  appName: 'ניהול משימות',
  webDir: 'www',
  server: {
    url: 'https://task-manager-ytca.onrender.com/mobile',
    cleartext: false,
    androidScheme: 'https',
  },
};

export default config;
