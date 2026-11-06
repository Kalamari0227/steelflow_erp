export {};
declare global{interface Window{completeHandlingQA:{state():unknown;sample(ms:number):unknown;play(speed?:number):unknown;hold(blocked:boolean):unknown;dispose():{loaded:number;disposed:boolean}};}}
