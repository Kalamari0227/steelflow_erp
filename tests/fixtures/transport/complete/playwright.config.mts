import {defineConfig,devices} from '@playwright/test';
import {resolve} from 'node:path';
const run=process.env.STEELFLOW_COMPLETE_RUN,port=process.env.STEELFLOW_COMPLETE_PORT;if(!run||!port)throw Error('Explicit owned complete-source run required');
export default defineConfig({testDir:resolve('tests/assets'),testMatch:'transport.spec.ts',grep:/complete parked source/,workers:1,retries:0,maxFailures:1,forbidOnly:true,timeout:60000,outputDir:resolve(run,'test-results'),reporter:[['list'],['json',{outputFile:resolve(run,'assertions.json')}]],use:{...devices['Desktop Chrome'],channel:'chrome',headless:true,baseURL:`http://127.0.0.1:${port}`,viewport:{width:1440,height:1050},trace:'on',video:{mode:'on',size:{width:1440,height:1050}},screenshot:'on'}});
