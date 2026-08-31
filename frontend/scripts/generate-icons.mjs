import { deflateSync } from 'node:zlib';
import { writeFileSync } from 'node:fs';

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const name = Buffer.from(type);
  const length = Buffer.alloc(4); length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4); checksum.writeUInt32BE(crc32(Buffer.concat([name, data])));
  return Buffer.concat([length, name, data, checksum]);
}
function png(size) {
  const signature = Buffer.from([137,80,78,71,13,10,26,10]);
  const header = Buffer.alloc(13); header.writeUInt32BE(size); header.writeUInt32BE(size, 4); header[8]=8; header[9]=6;
  const row = Buffer.alloc(1 + size * 4);
  for (let x=0; x<size; x+=1) { const i=1+x*4; row[i]=23; row[i+1]=37; row[i+2]=84; row[i+3]=255; }
  const raw = Buffer.concat(Array.from({length:size},()=>row));
  return Buffer.concat([signature, chunk('IHDR',header), chunk('IDAT',deflateSync(raw)), chunk('IEND',Buffer.alloc(0))]);
}
for (const size of [192,512]) writeFileSync(new URL(`../public/icon-${size}.png`,import.meta.url),png(size));
