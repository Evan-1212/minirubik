#!/usr/bin/env python3
"""Independent 3-D sticker rotations versus executable LED frames (Unicorn).
Supplementary checks only; not pinned-Ripes GUI evidence or official counts.
Requires unicorn==2.1.4, pyelftools; optional --preview requires Pillow.
"""
import argparse
from collections import Counter
import hashlib
import json
import random
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_INTR, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_X0, UC_RISCV_REG_PC

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent/'build/led'
POSITIONS = [(-1,1,1),(1,1,1),(1,-1,1),(-1,-1,1),
             (1,1,-1),(1,-1,-1),(-1,-1,-1),(-1,1,-1)]
NORMALS = [(0,1,0),(0,0,1),(-1,0,0),(1,0,0),(0,0,-1),(0,-1,0)]
ORDERS = [(0,1,2),(0,3,1),(5,1,3),(5,2,1),(0,4,3),(5,3,4),(5,4,2),(0,2,4)]
PALETTE = [0xffffff,0x00c050,0xff8000,0xff2020,0x2080ff,0xffff00]
NET = [(0,(7,4,0,1),9,0), (2,(7,0,6,3),0,7),
       (1,(0,1,3,2),9,7), (3,(1,4,2,5),18,7),
       (4,(4,7,5,6),27,7), (5,(3,2,6,5),9,14)]


def stickers(state):
    """Import a legal arbitrary input into geometrical sticker coordinates."""
    labels = [0]+[int(c) for c in state[:7]]
    twists = [0]+[int(c)-1 for c in state[7:]]
    return {(POSITIONS[i], NORMALS[ORDERS[i][k]]): ORDERS[labels[i]][(k+twists[i])%3]
            for i in range(8) for k in range(3)}


def rotate(vector, face):
    x,y,z = vector
    return [(x,z,-y),(-y,x,z),(z,y,-x)][face]


def physical_turn(s, face):
    # No solver transition or twist table in this geometrical rotation.
    def active(p):
        return p[0]==1 if face==0 else p[2]==-1 if face==1 else p[1]==-1
    return {(rotate(p,face),rotate(n,face)) if active(p) else (p,n):c
            for (p,n),c in s.items()}


def framebuffer(s):
    fb = [0]*(35*25)
    for face,corners,x0,y0 in NET:
        for j,corner in enumerate(corners):
            c = PALETTE[s[(POSITIONS[corner],NORMALS[face])]]
            for dy in range(3):
                for dx in range(4):
                    fb[(y0+3*(j//2)+dy)*35+x0+4*(j%2)+dx]=c
    return fb


class Machine:
    def __init__(self, elf):
        self.uc=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
        self.uc.mem_map(0,0x400000)
        with elf.open('rb') as f:
            e=ELFFile(f)
            self.entry=e.header['e_entry']
            self.sym={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
            for seg in e.iter_segments():
                if seg['p_type']=='PT_LOAD':self.uc.mem_write(seg['p_vaddr'],seg.data())
        self.frames=[]
        self.writes=0
        self.low=self.sym['__stack_top']
        self.exited=False
        def intr(uc,n,_):
            assert n==8 and self.reg(17)==10
            self.exited=True
            uc.emu_stop()
        def write(uc,access,address,size,value,_):
            if self.sym['__stack_bottom'] <= address < self.sym['__stack_top']:
                self.low=min(self.low,address)
            if 0x200000 <= address < 0x201000:
                assert size==4 and address%4==0 and address+size<=0x200000+3500
                self.writes+=1
            if address==self.sym.get('led_frame_count'):
                if value:
                    assert value==len(self.frames)+1
                    self.frames.append(list(struct.unpack('<875I',uc.mem_read(0x200000,3500))))
        self.uc.hook_add(UC_HOOK_INTR,intr)
        self.uc.hook_add(UC_HOOK_MEM_WRITE,write)

    def reg(self,n):return self.uc.reg_read(UC_RISCV_REG_X0+n)
    def run(self, status=0):
        self.uc.emu_start(self.entry,0x300000,timeout=30_000_000,count=50_000_000)
        assert self.exited and self.reg(25)==0x600d and self.reg(26)==status
        length=self.reg(27)
        if status:return b''
        return bytes(self.uc.mem_read(self.sym['result_path'],length))
    def call(self,name,args):
        for n in range(1,32):self.uc.reg_write(UC_RISCV_REG_X0+n,0x12340000+n*37)
        self.uc.reg_write(UC_RISCV_REG_X0+1,0x300000)
        self.uc.reg_write(UC_RISCV_REG_X0+2,self.sym['__stack_top'])
        self.uc.reg_write(UC_RISCV_REG_X0+3,self.sym['__global_pointer$'])
        for i,a in enumerate(args):self.uc.reg_write(UC_RISCV_REG_X0+10+i,a)
        saved={n:self.reg(n) for n in [2,3,4,8,9,*range(18,28)]}
        self.uc.emu_start(self.sym[name],0x300000,timeout=2_000_000,count=100000)
        assert self.uc.reg_read(UC_RISCV_REG_PC)==0x300000
        assert saved=={n:self.reg(n) for n in saved},'Renderer ABI clobber'
        return self.reg(10)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preview',action='store_true')
    args=p.parse_args()
    cases=json.loads((OUT/'cases.json').read_text())
    results=[]
    for case in cases[:len(cases)//2]:
        name=case['case']
        cli=Machine(OUT/(name+'-cli.elf'))
        renderer=Machine(OUT/(name+'-renderer-test.elf'))
        path=cli.run()
        assert renderer.run()==path,'Core result/path differs across renderer switch'
        state=stickers(case['input'])
        expected=[framebuffer(state)]
        for move in path:
            assert move<9
            for _ in range(move%3+1):state=physical_turn(state,move//3)
            expected.append(framebuffer(state))
        assert renderer.frames==expected,'Geometrical sticker/frame mismatch'
        assert expected[-1]==framebuffer(stickers('12345671111111'))
        assert renderer.writes==875+288*(len(path)+1)
        assert renderer.sym['__stack_top']-renderer.low<=96
        results.append(dict(case=name,input=case['input'],path=list(path),
                            frames=len(expected),mmio_writes=renderer.writes,
                            stack_written_bytes=renderer.sym['__stack_top']-renderer.low,
                            frame_sha256=[hashlib.sha256(struct.pack('<875I',*f)).hexdigest() for f in expected]))
        if args.preview and name=='distance11':
            from PIL import Image
            images=[]
            for frame in expected:
                im=Image.new('RGB',(35,25))
                im.putdata([(c>>16,(c>>8)&255,c&255) for c in frame])
                images.append(im.resize((560,400),Image.Resampling.NEAREST))
            images[0].save(OUT/'distance11-preview.gif',save_all=True,append_images=images[1:],duration=700,loop=0)
    # Exercise every move ID from randomized legal states, checking every pixel
    # against geometry rather than another copy of the source/twist table.
    rng=random.Random(20261007)
    m=Machine(OUT/(cases[0]['case']+'-renderer-test.elf'))
    checks=0
    for _ in range(30):
        perm=list(range(1,8));rng.shuffle(perm)
        ori=[rng.randrange(3) for _ in range(6)];ori.append(-sum(ori)%3)
        state=''.join(map(str,perm))+''.join(str(o+1) for o in ori)
        for move in range(9):
            m.frames=[]
            m.uc.mem_write(m.sym['cube_input'],state.encode()+b'\0')
            assert m.call('led_begin',[m.sym['cube_input']])==1
            m.uc.mem_write(m.sym['result_path'],bytes([move]))
            m.call('led_animate',[m.sym['result_path'],1])
            physical=stickers(state)
            for _ in range(move%3+1):physical=physical_turn(physical,move//3)
            assert m.frames==[framebuffer(stickers(state)),framebuffer(physical)]
            assert Counter(physical.values())==Counter({c:4 for c in range(6)})
            checks+=1
    invalid=Machine(OUT/(cases[0]['case']+'-renderer-test.elf'))
    invalid.uc.mem_write(invalid.sym['cube_input'],b'11345671111111\0')
    invalid.run(status=1)
    assert invalid.frames==[] and invalid.writes==0
    wrong_length=Machine(OUT/(cases[0]['case']+'-renderer-test.elf'))
    wrong_length.uc.mem_write(wrong_length.sym['expected_length'],struct.pack('<I',1))
    wrong_length.run(status=4)
    assert len(wrong_length.frames)==1
    result=dict(status='PASS',scope='Supplementary Unicorn and independent 3-D geometry; not Ripes GUI',
                complete_program_cases=results,random_state_move_checks=checks,
                emitted_half_and_inverse_turns_are_one_frame=True,abi_checks=True,
                mmio_bounds=True,invalid_input_status=1,length_failure_status=4,
                required_local_checks=['Pinned Ripes GUI source assembly','LED GUI animation','CLI/GUI path comparison'])
    (OUT/'supplementary-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
