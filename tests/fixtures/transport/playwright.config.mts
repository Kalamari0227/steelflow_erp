import {defineConfig,devices} from '@playwright/test';
import {resolve} from 'node:path';
const run=process.env.STEELFLOW_TRANSPORT_RUN,port=process.env.STEELFLOW_TRANSPORT_WEB_PORT;
if(!run||!port)throw new Error('Owned transport QA environment required');
export default defineConfig({testDir:resolve('tests/assets'),testMatch:'transport.spec.ts',workers:1,retries:0,forbidOnly:true,timeout:180000,outputDir:resolve(run,'test-results'),reporter:[['list'],['json',{outputFile:resolve(run,'assertions.json')}]],use:{...devices['Desktop Chrome'],channel:'chrome',headless:true,baseURL:`http://127.0.0.1:${port}`,viewport:{width:1440,height:1050},trace:'on',video:{mode:'on',size:{width:1440,height:1050}},screenshot:'on'}});
