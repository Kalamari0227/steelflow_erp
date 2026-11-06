import {defineConfig,devices} from '@playwright/test';
import {resolve} from 'node:path';

const evidence=process.env.STEELFLOW_FINISHING_RUN_DIR,port=process.env.STEELFLOW_FINISHING_WEB_PORT;
if(!evidence||!port)throw new Error('Use the owned finishing runner');
export default defineConfig({testDir:resolve('tests/assets'),testMatch:'finishing.spec.ts',fullyParallel:false,workers:1,retries:0,forbidOnly:true,timeout:60000,expect:{timeout:15000},outputDir:resolve(evidence,'test-results'),reporter:[['list'],['json',{outputFile:resolve(evidence,'playwright-results.json')}]],use:{...devices['Desktop Chrome'],channel:'chrome',headless:false,serviceWorkers:'block',baseURL:'http://127.0.0.1:'+port,viewport:{width:1440,height:1000},trace:'on',video:{mode:'on',size:{width:1440,height:1000}},screenshot:'on'}});
