/** Fixed canonical GO07 scalar samples, without a wall-clock animation. */
export function batchCar(p:number):number{if(p===0||p===1)return -2;if(p===.25||p===.85)return 0;return p<.25 ? -2+8*p : p<.85 ? 0 : -2*(p-.85)/.15;}
export function batchBell(p:number):number{if(p===.25||p===.85)return 2;if(p===.4||p===.7)return 0;return p<.25 ? 2 : p<.4 ? 2*(.4-p)/.15 : p<.7 ? 0 : p<.85 ? 2*(p-.7)/.15 : 2;}
