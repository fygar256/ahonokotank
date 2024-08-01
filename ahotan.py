#!/usr/bin/python3
import supertext as st

(lx,ly,ld,lbx,lby,lbd,lp,rx,ry,rd,rbx,rby,rbd,rp)=(0,0,0,0,0,0,0,0,0,0,0,0,0,0)
dirs={ '8':[0,-1],'2':[0,1],'4':[-1,0],'6':[1,0] }

def ahotan_map():
    (x,y)=(0,0)
    st.clearscreen()
    st.color((0,0xff,0))
    f=open("/home/gar/org/attic/ahotan/ahotan.map","rt")
    for a in f:
        x=0
        for b in a:
            if (b=='\n'):
                continue
            if b=='＃':
                st.locate(x,y)
                st.putchar(chr(0x90))
            x+=1
        y+=1
    f.close()

def disptank(x,y,tank):
    st.locate(x,y)
    st.color((0,0xff,0xff))
    st.putchar(chr(0x80) if tank=='left' else chr(0x81))

def place_tanks():
    global rbx,rx,ry,rd,lbx,lx,ly,ld
    lbx=0
    ly=12
    lx=2
    ld='6'
    rbx=0
    rx=37
    ry=12
    rd='4'

def erasetube(x,y,d):
    st.locate(x+dirs[d][0],y+dirs[d][1])
    st.putchar(' ')

def disptube(x,y,d):
    st.locate(x,y)
    st.putchar(chr(0x82) if d=='8' or d=='2' else chr(0x83))

def tanksub(x,y,d,d2,key):
    (nx,ny,nd)=(x,y,d)
    (dx,dy)=(dirs[d2][0],dirs[d2][1])
    if st.getkeys()[key]==1 and st.peek(x+dx,y+dy)==chr(0):
        if d==d2 and st.peek(x+dx*2,y+dy*2)==chr(0):
            (nx,ny)=(x+dx,y+dy)
        else:
            nd=d2
    return (nx,ny,nd)

def erasechar(x,y):
    st.locate(x,y)
    st.putchar(' ')

def rightbullet():
    global rbx,rby
    if not rbx: return
    (dx,dy)=(dirs[rd][0],dirs[rd][1])
    (ax,ay)=(rbx+dx,rby+dy)
    erasechar(rbx,rby)
    nc=st.peek(ax,ay)
    if not nc in chr(0)+chr(0x80)+chr(0x81):
        rbx=0
        return
    rbx=ax
    rby=ay
    disptube(rbx,rby,rd)

def leftbullet():
    global lbx,lby
    if not lbx: return
    (dx,dy)=(dirs[ld][0],dirs[ld][1])
    (ax,ay)=(lbx+dx,lby+dy)
    erasechar(lbx,lby)
    nc=st.peek(ax,ay)
    if not nc in chr(0)+chr(0x80)+chr(0x81):
        lbx=0
        return
    lbx=ax
    lby=ay
    disptube(lbx,lby,ld)

def righttank():
    global rx,ry,rd,rbx,rby
    erasechar(rx,ry)
    erasetube(rx,ry,rd)
    (rx,ry,rd)=tanksub(rx,ry,rd,'8','8')
    (rx,ry,rd)=tanksub(rx,ry,rd,'2','2')
    (rx,ry,rd)=tanksub(rx,ry,rd,'4','4')
    (rx,ry,rd)=tanksub(rx,ry,rd,'6','6')
    if st.getkeys()['0'] and rbx==0:
        (rbx,rby)=(rx+dirs[rd][0],ry+dirs[rd][1])
    disptank(rx,ry,'right')
    disptube(rx+dirs[rd][0],ry+dirs[rd][1],rd)

def lefttank():
    global lx,ly,ld,lbx,lby,lbd
    erasechar(lx,ly)
    erasetube(lx,ly,ld)
    (lx,ly,ld)=tanksub(lx,ly,ld,'8','e')
    (lx,ly,ld)=tanksub(lx,ly,ld,'2','c')
    (lx,ly,ld)=tanksub(lx,ly,ld,'4','s')
    (lx,ly,ld)=tanksub(lx,ly,ld,'6','f')
    if st.getkeys()['z'] and lbx==0:
        (lbx,lby)=(lx+dirs[ld][0],ly+dirs[ld][1])
    disptank(lx,ly,'left')
    disptube(lx+dirs[ld][0],ly+dirs[ld][1],ld)

def dispscores():
    st.locate(6,0)
    st.bgcolor((0,255,0))
    st.color((255,255,255))
    st.putstr("Left:")
    st.putchar(chr(lp+0x30))
    st.locate(29,0)
    st.putstr("Right:")
    st.putchar(chr(rp+0x30))
    st.bgcolor((0,0,0))

def disp_hit(x,y):
    st.color((255,0,0))
    st.locate(x,y)
    st.putchar('*')

def keywait():
    st.locate(14,24)
    st.color((0,0,255))
    st.bgcolor((0,255,0))
    st.putstr("Hit ENTER Key")
    st.refresh()
    while(1):
        ret=st.getkey('return')
        q=st.getkey('q')
        if ret:
            return
        if q:
            exit(0)

def match():
    global rp,lp
    ahotan_map()
    dispscores()
    place_tanks()
    while(1):
        k=st.getkeys()['q']
        if k==1:
            exit(0)
        if rbx==lx and rby==ly or lbx==lx and lby==ly: # right point
            st.color((0,255,0))
            st.bgcolor((0,0,255))
            st.locate(14,0)
            st.putstr(" Right Point ")
            rp+=1
            dispscores()
            disp_hit(lx,ly)
            if rp<=2:
                keywait()
            return
        if lbx==rx and lby==ry or rbx==rx and rby==ry : # Left point
            st.color((0,255,0))
            st.bgcolor((0,0,255))
            st.locate(14,0)
            st.putstr(" Left  Point ")
            lp+=1
            dispscores()
            disp_hit(rx,ry)
            if lp<=2:
                keywait()
            return
        righttank()
        lefttank()
        rightbullet()
        leftbullet()
        st.refresh()
        st.sleep(1.6)

def main():
    global rp,lp
    st.setscreen("AHONOKO TANK")
    rp=0
    lp=0
    while(1):
        match()
        st.locate(13,0)
        st.bgcolor((255,0,0))
        st.color((255,255,255))
        if lp==3:
            st.putstr("  LEFT  WIN  ")
            keywait()
            return
        if rp==3:
            st.putstr("  RIGHT WIN  ")
            keywait()
            return

if __name__=="__main__":
    main()
    exit(0)
