"""Canonical, immutable MCP capability registry and startup-static public profiles.

The embedded definitions are a lossless representation of the operator-authorized
Batch 1 normative matrix. Runtime consumers derive membership and policy sets from
this module; enforcement remains in the broker, origin-auth, safe-mode, scope, path,
and feature-gate layers.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
import re
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from types import MappingProxyType

MATRIX_SHA256 = "6f758afd1f46c3ef4a5c06763faf21b2e4d8a2c01ed347a52b96a18f6db3c08e"
CAPABILITY_PROFILE_ENV = "HB_MCP_CAPABILITY_PROFILE"


class Authorization(StrEnum):
    READ_ONLY = "read_only"
    CONTROLLED_WRITE = "controlled_write"
    CANONICAL_WRITE = "canonical_write"
    ADMINISTRATIVE = "administrative"
    INTERNAL = "internal"
    PROHIBITED = "prohibited"


class SideEffect(StrEnum):
    READ_ONLY = "read_only"
    STAGED_WRITE = "staged_write"
    CANONICAL_WRITE = "canonical_write"
    ADMIN_WRITE = "admin_write"
    WRITE_PROXY = "write_proxy"


class Exposure(StrEnum):
    DIRECT = "direct"
    GATEWAY = "gateway"
    NONE = "none"


class Lifecycle(StrEnum):
    ACTIVE = "active"
    COMPATIBILITY = "compatibility"
    LEGACY = "legacy"
    DEPRECATED_ALIAS = "deprecated_alias"
    INTERNAL = "internal"


class CapabilityProfile(StrEnum):
    FRONTIER_V1 = "frontier-v1"
    LEGACY_V12 = "legacy-v12"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    registered_name: str
    semantic_capability_id: str
    capability_version: str
    handler_module: str
    handler_symbol: str
    schema_provider: str
    authorization_class: Authorization
    side_effect_class: SideEffect
    direct_exposure: bool
    gateway_exposure: bool
    profile_membership: tuple[CapabilityProfile, ...]
    group: str
    feature_gate: str | None
    lifecycle_status: Lifecycle
    alias_status: str
    alias_target: str | None
    deprecation_status: str
    replacement: str | None
    description_authority: str
    result_bounds: str
    attestation_probes: tuple[str, ...]
    exact_test_node_ids: tuple[str, ...]
    indirect_test_node_ids: tuple[str, ...]
    compatibility_disposition: str
    planning_rationale: str
    source_evidence: tuple[str, ...]

    @property
    def exposures(self) -> frozenset[Exposure]:
        values: set[Exposure] = set()
        if self.direct_exposure:
            values.add(Exposure.DIRECT)
        if self.gateway_exposure:
            values.add(Exposure.GATEWAY)
        return frozenset(values or {Exposure.NONE})

    @property
    def schema_sha256(self) -> str:
        match = re.fullmatch(r"live FastMCP schema hash:([0-9a-f]{64})", self.schema_provider)
        return match.group(1) if match else ""

    @property
    def is_alias(self) -> bool:
        return self.alias_status == "alias"


@dataclass(frozen=True, slots=True)
class CapabilityRegistry:
    definitions: tuple[CapabilityDefinition, ...]

    @property
    def by_name(self) -> Mapping[str, CapabilityDefinition]:
        return MappingProxyType({item.registered_name: item for item in self.definitions})

    def get(self, name: str) -> CapabilityDefinition | None:
        return self.by_name.get(name)


# Losslessly compressed authorized CSV. Keeping it in the implementation avoids a
# second tracked matrix artifact while preserving every ratified field verbatim.
_MATRIX_B85 = (
    "c-ri}>vkJCmL~dtp282HRN;PU&6>5cvs~4=IxDkIrgLiM7Z)xY63Z0H;>EV=h0cSV7dsn>2;Rh?NQxmV<>>0PO%eeh0DRxRU}Iwj"
    "x5N1YW)KHscMn%{xOd~lFbsm5IzJo@7Y~DByxREm31;)*WPEk!#&HC*!TlsIN3i-hf4KLP(bYWMVNHYSZ1QOsVRq$~i@V8e_;0ts"
    "X9r>A=JTsL{xX1+AS~){;&7Hfz?bP{zMR3;ty{on_ptr~>r2BC4DR9HV?XYO)2rLrWI4S`;1*b5ke|334YAILfaT^3{Ca-nMngB>"
    "{;+VfTUcC0m|~Mvuj=1tFdex7_b|>s&%<muEkD<<uz0`{^W|tU@RQ{@VttDR<VSNE?4O7E6?}2{8u{zNc!DoE#A3s7{dU`5hspgE"
    "pRETs4(Ir$!(7)D_F_C9j&BFEQn$lFo==vufMb@&bR6J+xZz;3TuhgXInLKC4wln7%obO7{(3!O*KT-S7rM@cuIobdnp~5s`7HeD"
    "&JS?#aT(yu|7nb4b04OET1+OR!K|!~s{KFB>ZLNMiwts+`StYSs-+vF;U{?a7dK!0?T5d=s}{t&J2$`kk02t^E&&&y@&6^4o&Z-#"
    "s1OwX+a@PmN-|2Ty#z**wHA_(3Y^xUaXF4B<6&^4!DpNhc=UNOTh@P!;MRqQ?><ph|FiCCUGTsDbAX*2eE-u=zx-qH{f~oRe*f_I"
    "-#`2|_{Xn5et5q<H&^4yVo=u3RrzPLav)w^H7_~w_~M@+zS|tQ8Vlbc3~)f=P4nZ!yH8kMEM@S!e=Tu&#4Cg!uHO0L-EfQ(G8*Am"
    "dBM#8RF(~lXTxxpmnN>Dydo!9Xtuyf_>cc61!izRSwNW{9O_(X<B{^tW!i2w>Kq$H`)HU8G&mdh*)ZP1y4sBy#ugm*Z7>;+9&o+m"
    "YW#w4lh<igJ@P<C(!;!95t~mFT(j}i78~f#;GYPZIS%)Dh$OXcW1Jy58cjZr@~V7Pf3rXb!|^9<Xfk^kq#=T6?>h~V5AL9PrItae"
    "*F567rixpbZw|YQ^MS+n$V;PCfqa8YJkukbP*KG}Sl@Iq!;Wp0+FQ-)B{p7cIt3h{#bi(~`2xz}y!6e_CLdvZY*hhY3<tNWp)4p^"
    ";<6qM(rhwb+-K^W9a~qN<b{*_F~>E&82%gU%@c_byTe&R#yGa7<uvA{HA!19I72BmMv$#KxwpFU{4-KmoVm1k-u&&aXm|cLOYN<u"
    "Azu9E)5a98zTVff6DryyqJfK86=fS`3xy9p-@zDx>ilR2M|Ir+=Ni5&aHhh?XAN3}FwDwBmfwiT=TwydqR0MRwvL_YYYOapc!*;%"
    "8Vzr=Abw6K_Sdu1k<CK;DtZ2RPO^HlUBO@;CR3<>8F)9#N+RO^{t1fQsi`WwSyf?etZQ+Hs@v^druK(S;)V0~);Js94l4z0U2hSd"
    "*a>7a#DD&8G}`2Jzg(1;$InI4Op{UEPgeh0x}qpOWAq+Xu`_@5@B1FDC3daZ?iEiJ3pcb^(fgTIA^TPXF&It4M`)>L4sI6i3f|#)"
    "G}&I)&Is)m++W$JA$)#bceZPI)QSA_z6V#e4o1WKVWtM`@ZA{Z8*elzrqRC}aan0B=T^2Zlj}i=i!<kzak#itl{i!z>mm!{`(<Ut"
    "%+GD0g8FB)bS9q%J}<B`w3Q0cF1k*xI=LZAtuUI*v0juW%W+-_S$rW?ptPFJmeXo(_b!6kibAP2M%8jMd(MJtuWM&%?H1fuS<zR~"
    "=$q8@uz_IYwvXe<=kW&jRvo=}GlVhDC`$PyYKx!tcJuRO_Aw#r&YxE4O9PvAAf4P#^Iwoq0^Kce`0s~U5Xn2M{p%V5*Z)J^&GIVu"
    "ZaU9usH@4kdhj@VW=EfAys;SSnky^malv-O;sguf7=`^wW%U@X@fc0+7>(>WW$OtY=m_oPpzd)<8F*T(9~P@eiMt~O&_Tg)GC>{5"
    "3P<AoDe#^K%&TdB{n;mYx6GE&yR|pu=G}PmF2V?k_o4C5LA?5@6nVGh`gn&xN-n^=rn-3Z4!(rZGD3WpHNtnr92~+7tA3ZY6KwvS"
    "dpAM?p1oT<Omi{!|NXx%!u1s;-yxK6V!uNWBbH|0ZQ3aF>wnHC;~PqwLSZr*l`-5~jDMG%Oy4CpU*Jf6S7`COtV`Cvi|yYlPfY!="
    "lHaYpWZyO3w(lC}8g_3n8-BSC^H2X{4ar+rY%#&EudOL~jRmi(g4b2SOZwZ|yVL4(lc1>t8KjIJ|E)Q-K1JzeaFRM_81jIQJ|-Gt"
    "U?x!+ffGTs@Bq}%tIPy5q{pjb8e~zi*UfgbDz`<LD^J^Rzy0{zhwp#>F!=t54?q6$^8i2m_5E*0yV_O@EyHp2Zi2{$X2kH*z9si^"
    "-nl1yJNHAJxAAS`$_gWJIEp7YhbpN*gT-<-9$?qpK{jY;W3Zez%X2OKHyWt9Z;)YwW)q}I_M^k%>O>)UTnEmeq#rid#&>z;y=xZP"
    "_5#>tr3lF_M~f9Zy^BM%L$j9h)@W!DhP4binvky7kGu#qZFI4fq?9DVSm4g^WGHjin8*`YZao#?BQ8!Ctp^d6fe<})6qE=;GUFYg"
    "x+ke;lhh-QIp*0O)SZAj+c1x}^V$(zmwy>J*NwGenQHBbv%y75qYy$H0?9<DWkB#6VVnc11WBNi5FiYX-gu7+i6)YP?6KTq`3+%t"
    "xPbc;gmYE=WsqF8)e7X8n6jGi<j{T)V9<1+9ym=ZG7%IP$=S$J3_D@DHYPC3P;eWjqYe~o59A)mZwScq<^8>zJsc0^=7E<1bJJQY"
    "oWWB{xg^#Z<E=KHlbCgD#ziy^AW_Ca2cxw}B+}qa)Ye7G4GEFU(8IZh^B)_|Wp^%3X0@C4Ad*YO9G1PV%XS9h-A=XQH*xO*AYvu3"
    "z>?scB&E>^)`Ds7V{~3vL5NmB1QsD!grN<MUpSJe-GJ?30AG#Wr^jgh`TPI<TH@mV(=Ec?JGy%APxVf~yApo+-5eJ0%A&<Zx~`{p"
    "iFXF6vf=tPnyO;m0;y`F9YazCVm-0iYR!mAUT~r)RU~Mhz*x$e7ADDLqlt=1jhe1O<<~Q&9CvRAL+6B~tw*?o4Pa06hHJQU<1F8g"
    "sIkXjCm7t=6F!W>s^E1g*c}cxyVHt97l{iB5@SItL1VBAXh8Ter>F%TSxTN;;iRE7@Zb;@l4ug7w~~i5wxzbV&L3m*hhKjF@c#dN"
    "82tVFAO8D|X`?M+oSR=C-eP*9qGo@qRJ6Uxb#+#dMoV+OCfo&O9O0qbB#y2<RC~JC?x7;gQknJLXt`5p&PHnj_Y|Cx#&QvuV%~e6"
    "rFXz$&M+SxWdUqrz<Lttm_)96RKFmqo4~JwSY8$C48f}w+GA2uiX37j+6NjXr$!0wqc&dV-6AH4*Iufm@W&Ks^olYerHUT7iHRMr"
    "hVR6}Jx1)G-~aIAZ`lp?xA%Yh<=6lF3f1!*^qNH_j6cCB2h%@_zif_7HFCJAc;IHYgW<RUV7~e_4Pg|w;&Gey2hHJ4H`@vt$=-=o"
    "nJQFvvx#|iH~|0nH;l2p2w%#K>=o&i{LhsPa~$1(k}vCq${D3u2}oJ3qWSs_a-hkiI+au(`#b5Z$vO<DE-;J(C}Dk72<<YzPczDA"
    "*8Eg}PiqyYh4|p8FYhZw3Rhg^bY6$!mP4qUZ#joiIZKD=%=rC0%!e^>;?8g5-i>fo+~dm*n^S+yAT-ZCqjnsI*$_U#dZO2_Go4JA"
    "Ss>1H%jIBO6}G(`pWj{)t=l7ZH~EZnRImmmmbn_cF5{yQ)?HVcrDx_^6a*WKXVvqSI75`ra`ZgTG(L!Lbb-pNb%otsPeEQpM{?Cs"
    "gmVIAoF4gn<eE5biq9C=%}2I^+SlR5gWF~HnDri$jufRFhJRQ~DkZv8kxKQg`Vo<uf=`4<#T6v3jPY86XP^mXiQD7@=p?;$T7h=l"
    "5gtKVXS@;+{25zyo97euY}Nhz+dtm_I{5Ri-~Z*qTidGJf1dY*nBDyq9JklE^K5SmT@>O+M#q-2FA)~I+o^T~DNta*h*p9iw1be5"
    "`)Cd2$O>p8X&tFZc^4xlG^1klK}QmdF=#QV7<&SEHUaebeFgYEA`rF$Z`Tp9Tit1w+h7P|K?xQ-mzFw4jFmvB1L{<Eb^sB?3zIYe"
    "u|a!;Z!#i8Zdf3+hiwnrw*cEYgkz=ds%Xd1UA5C58xS~C&QK~*h@vHFAPOH8b6Tswyl0XVt3i6hlI7Moi~oyWM5YktLiOP7!TTn_"
    "dqkXTjoq#TT(>*aid+^w_bMvqiT098<v?heIMW~`LR14Yf}$=RQ4rhYEa%pGPJD<gQ3yS9d*uGHky|Cx#Cn@Ey-$batsc3qQy_F4"
    "p4ZaFR!|F>7y&APN6n+Kj8Z~bK<TVBfj|IIT$8}CfR`Nqq$(Lyq%BE41#M0Tb=9xOX#Vy6|Nim)Ki(FMck>|~h2PafJ#a4t+$Ial"
    "L8z_@bq3B=3$1XpAhnGkj5eBhDS{^?+qi^#XQR-ZO3>gzP;Yo(JWw=*!83}u_gMYua9s825g`Ba{{5f-^ZOtE`)xt;aZ<wLebA4e"
    "y<EzOrtVYHMYJRr>N7=r9d<d!kG7h!u3c%nooc5XV+}WfTZUZYNI)&#Swo`Hn#)M23@HD>P^LXtP(ewSPr=v_rSVkLo^np7oTK!B"
    "jmLVdUL32qf+qL(Fpfv;T&-qe_o435yW3)Wkgj7gA2<cWg*D6s6*X9C2w@5p1uHoX7FBpoiF7`hWQ+&~gpfRlbdF!Ghj9<%uMXp5"
    "+-R#A=-iX`s9WvnTM|blpMZ>kxTH*qJ_+dvqd|#;Dt<(JI}qdWJFr1B5o5F{l@kS~N$BC)!}Sjc*XmlBBc*LqxO=!ZEwyKLK<Sx?"
    "kzOY2gRxErXQWfc<_t_|v>R`N*HMb(&>VM4d6ftj7A^>(br07bu74c3Ze}IU-h_WvySfKayPe5+{Y+=zZR=#ahU|qUnkCPS7gSN|"
    "(T<f2LI@V6Dt^yNvQhw}_%8&o<-stoR4{^jlTOF*W)~mh_{X0=y#MK^AOHIP=O5m`EiCW9bK`hF+y3W|;)9(>drs(>6OQqDwNOLn"
    "F0d!M+`cE4!$A@FNf9j*^W19BbNVL8>6(NL36czkn`lVT%2SmsZLR?S4$AwUD4s_YJ<wkx(4RiP-iGszkFp=`aC;ycQ;tYw!6wbX"
    "$%t}aIHw^B6=m>-c+~lIa*j%?m=OvI!I}VuNfLtWQQo8cjiCG(C)(CbbnZyo+r4({oC=u&muP?o)aaD~O@a?T^1#4w3dZ@wL_!&^"
    "X(TC^qTJ@Q@hnM2dnor%{^LTqI)yvP>ufkWVmGTkwYycmGa&ElTq}+_6C^Mq!6+{@0+c1f3{65uhDg>q>2Z#ViGp(G(0r$fYa1;~"
    "hA0%)$0w|4%Tw`c(^ItFL|KpTQ3zZ;+aGuC5Qq7w`>_~YmF*gTtA-BbJ$0NrV}L{*M5NRxLI^MxnM*wHP9-WGFrg?&BREwYq$H7Z"
    "p1g9j$6k-Uua3Pjs!qq?u9WK<bET1XZ*<U}O2!g`#YYizK)DyCkz7#8jWk}Sm?&zlCZZf<krT^JATb&mv<^Mq4(3p7%N;ac-Osu|"
    "d14ROmw@X8-*7OROr{6HnoC`mQk_9{-H~>0u(u&a?Oo(XuzZM^GjC<0-U#izb3yZ<0xF=|h3ri-R+m^w6p@lE@=aw?d&vY`RXVBF"
    "4Ca(cyLqIpy2@VE(?S=tkVhS6#iw$J7dDD@MhqKmv@?U@L?{`85sGkd#&Iwj72^;XO%$?)$^=9wA`vnlpQIvqo^%u>MaI7=W;h4i"
    ">q&SD+&yf+B5dnxqz_`YDbpEXn+DpQOUeSX2ucOsQJ*3Jfe4mF%YvrXQq8<!9_2R`5t!3x*D@z)N?yx&#!1JfOOMd{|NQ>_Pd|S6"
    "zi-PmyuM8Q<am!qj~+IuPfc*XuD*9VUl{Ypgnu-{-*vdhPM6y6L=dR7GtHRH8O)R9(m7+O2`b;Or)7YMwl`rUDHPm1GLyI<Ob|&F"
    "0U>%KIFSgBa**{P?GB`ASTvCNQ7~N<?i{GAmRh0e84Hm?NP<T%xX=O7YG_2bDo3q~OhJ$daZ8D2LRkeWh7f>zW|-hTR4)qEUhuvi"
    "Odk`o(TsoR;TpT0YFEOEj4|;fT?}X_Q(}Nf<q}Ilf+h%V@1^pDagCyuDj?Cbgy@Dqf>gQ(bT51VSU5fA#8Wf=ogaAG?NlpHjYgpw"
    "UG{Pd#t@z|>6AFhe()SO>6PY;Q6H6rM7dBrY7tOjW+b1bpgm4|oc=LzI)l6*Vtp^{VVu@wubZ-+;dHlC?YqcE1u3<5V6`#H2PQ$H"
    "fg7C#BOw}LQAN&~G*Qw<@J3ti0aCCuI5d0v+iH7%a0if@gF{9scaOp12}o6Cuj{fMLTbBH?U16Vd`4@5(P$YpQ3YM4lhy{sVN77b"
    "3N$ox>iEEY(10S3I?fpiNNUf?h_}_X`M%tEzrFwd*B}0?+<5o?ttGqMegAV@$nAAp)}-CjPA`i)B90^PmDr(>m$+e~y`!zP6410|"
    "lw0W_F^PhjYeyB6f>;wRK?OP}!%`v?IE_+zCm48|-P1nbn%&dN<!I%|G@L!sUkvF-Y$NT$yzA|xmM$L1qzjSf3vaCrS`kYnWm1NO"
    "%D5pqUz#g;ij>ks94d=SIZLeeK`P-LH$A|6fWKjYKYe<57vCM98s6W*_T=|LIijfZoN7p3=m6kynmv*<_nHZiBpAeca+Cz=RX`hC"
    "QX_?z3}t<f?jGH57v0BfM(yIe^G&I?PPSYA(h6${W!fgAtVlW#<CTgCW^Vw%d#feGAF}L@0Lm#wJe4@v!5GqGyvO)k!g$F;j_)*`"
    "%!kLA;pN(bt@0gW`*G*mk2V@dO$;nLMg&s~bf8KL3nF-rv&nSyR0R`MqA1@1ZFHSe_obv$B#QKRT=aKb{9*8#_1I%@TFP~e&(cUM"
    "E)j{*I8Lqi!CK8ZvCLRaQ;3QPPnpXnkAW*MLSUAlxRr|VBx2sWBDTlnDY!hvm);}#6(RaK<+{3Ds(YP!t4r+}d4h~G!~hb28bV17"
    "!RExc$ynk;kcnAHF)0Jw8iiJKWDLJgBC+VD>!IC?+}97#Dm>#LFzX_n0kW>Y9f(Pi5G@5XW;In1K`NG`MSwc)(B4f^tKdxFD1^03"
    "LD}Gha7I`ns0(i=KxE%diL0T+&adILZ-h?}pHJ3W8?9~}HyYTi2?t;phi=@ojr9y~-S!E|jjkc&U^ZP0{3HW94r<Vq1~S%WxQ>r`"
    "{iD0khs|`yCWADY4T77+BWUFs%U+kV9rMe&Q|;GC<@gv90wj<Q4QMZ7c6>9z^G#CTqrf+S;$MPbQQ63(=Zplj%^fpFhCULlht$O("
    "^{Mb6PXA#cU5Z_oVx0kLqbuzOv1U2t7DaVfLSoLioT66CM6FfU3y{G|MI-YjCj??#a|N867=#O)%5Pg(uSd9~8$`fB5rNAwHiB#P"
    "xN3VKb^*lI4U}%S7~;4*aUh~8e!VW<88G*Bt^GVA$?=~&M~9|JsLt6al@H1rCAndiYqViOB*D1PQKZgmA-PP}MM4re!>nz3w`XhU"
    "AHV$i-+%e(mw&vmJ)zYbZ(zKc8T?ni*t$*%GS6TiOx?q1;^O?Nx_Yzs;$RN=cJO6!9F&{F-2=I4sa?*Je0!-g5TYiAXl|*}HaUVy"
    "si)CJp`B6AL<gR@pc65U#q6oVuLz3I9>(XuxSp56aK18CKi>@(kk>1=dR!$X3s8~kO?9>3Yc>7zD*yky7%juB2;@XSxv|wG^i=WE"
    "R56{5hT-8jrl`wyPZV`S?WZ6;iu4r0k;t@h#PO)}B`=93Z==GWRT9>ltP^k{0(Bx-h*AJ5=9b%@C(h!DYFY->4q_Ja1NZ`AS$fbT"
    "_ob10%=Xg?x}9%8J?d7wkWV2p6H$yiVToka2WExKm%3%=R5Foz?Ia5!@EEwHEO;e^HI^h51nI$h7I+b@Ykq}Up1YF3Z{hq1HTKW5"
    ";R3%nQrOp%T(Q774RMrf1>hbQu5G8QCxlBALauvIWl<d9H@64QNtbTa2^Z_4oshwvE*&@}Ek$CKTHz^ptCRu_R0bWB*4~*Ah0B}K"
    "6a_j>LB&7`izyHk>?znYj%I9k>=7M&|HFrztP?-{_5B;8gsnGUBl+WSG#bo54;SGsN9|Q)kOy-6ft%xN%u`W01oALtUcnmYE+IGI"
    "@SIT5QTfClC2VMap}Oe7timgbT+SN^t-T!^-E0Cb@@hw`3DBg0EC-);hIMxw4!`f|@6mJa<v91=4{w)~<-F{^;dkSYPf>64MA;a;"
    "uAb<Sf%kQ={S=MPQ3yokoQj5eRKutz%A*1nL508)Ps}41D@r7{UMZ`I6(SmHmDJFutLXP8IsjSYNXn-Oo<LV!^tvkA9jvyybReg("
    "VmY9Wa@1TR{!c(Yp%#(|fEEr5oH7X6&l!>j;sqK-!CM++RN50bU9s8j*dv7f@XOC1-v6Hu<+RFMQEU#0*CrSTJNVf>AP0_6mB2qH"
    "pDU;4#`a>K>V1-SYeXMAOY_&qsVFTKZ73=yJat&RdY1aJ+hVUST#U(@djg(dv30TT7;N3ffity?d!vK2RvI8wFijnm&Nu)TD5sWM"
    "LKBLAqEI)W!N(Z6=R#qbl;E4ZS*3<re&OL5=JNq1U-m^ql&Q;J5>(A0bB7xh{4S8CMp*3T<huQA@)0L~dv*uIalzNT*ankKdBKe*"
    ";~`Sv8BHvQqc~^=BCC|MVXk^PLt@!$)3shS^91d+KDYCFE(Dk^)*Dv;S|V2rP*Xz;oK)}W=IVKO=p4SOwcTpnEPu?QkoKCYlIP#+"
    "bMHoI=HBCA4`Vh`ALgsz+vd6X!P>KjFqcL_Q@bBG25&X0E9S@9oZ%1nDtGuGHhO`|ix!{zKb=gMS$)Y<e>>lin~XPjsL)!k`(3$t"
    "vVh%>v73`GLuy$|2baeg^M1y7_m)sM`oqkn#Z$^dRi;DDp=zLgS2oe;3<Ch;sL;x4ubonf8-rF437Tu^ArSm8$RLHI+)xd{Is%aF"
    "8M$fQc>WnXUU%%VH}~h?{_+0T!JmKq{x5Isfd1B-ALY&6eBkEz8qe_N?yu-5;kak3sr{AqhmD-<blvIhO}}yVVyw2Dj)oa@#Yg!R"
    "y)}ietHK@f+)lUJ2~PwQyg+WVjBsFH#T;@X6&g(<Qb<Iayq^UmNv#O@khJv<h;*JZt9!3$uPa<0RWP0n!`*$QX|7KDKY_0GLz{UB"
    "x<px9H`}j=q6T6}$ul3dPTD6QA~!zD5VYk9VHLR|N{B>NO4K>7xQ~>Bqgn*l`&6G+FE%D+JQ*PHCRk{;*i;9yFQH5<PD%*@TR&2?"
    "gUk9;kLz6T&3sXYNdVE~upXwARjKYcWYxrhOQJoMJQ}c0CIMVKr(+Z}3dkFm!fGd}XO?NjHMfFA;#~5YP+|j7@pRHy_305`{N?@o"
    "KmR9kMITpkIIg4_!DA|G${ttG>Bh|CI$m2;O4Gxy7Ll?sM18=@tL5xXS79Fgf7XXF4s-angK^`j?l`@*qwO5ev{0z;0T`+xD5ZjT"
    "3_lr{?*_HOYY{Eu5>-JNqi3A+q=O0xP<`a#bdKNb<71xx5!J$<e){pR?|=T`eeZQT>~*^IZpi-nPUrpo^&G|h?YT1#ZOv>yv#;Jd"
    ";{)oo<3cXS)Vur4)tL^kqc$2Iz4noB(X;%;SiagV!c`uhiUhCsm8z26vH4bqS{a-uVug|x)pSm%LUTSvq0oZ2K!b&x2{dsfIZ28T"
    "FxpwP=X26BPPrzD9q&kMi!*rj;RPpdqwf~4=iw*<J8g&jS^DLwsoodZ2_H=G6$hiqWcmaf<Z{<lx$d}NqciPH;5cDXiO7VM0<0HF"
    "F{c?#)F+c5F|Ry$RQbG%*=|o!2N}S43d#`kO@<zw7m#vV@W*QM>N^mz?xx%v|2@rdMO6^a)yd%uNA{%Wh)y_Sy3X5im?Sm}cE=K%"
    "t+eNR0qcU%h6)L2-f3-lP{M-K`A$v3rA?A68zl)mpC~nsIq&gH%YhhBJx!cX69)sW*0Z+}$MqRId3loP1CU;jB$`{G4-!OEs5^3K"
    "T4+zJYPi$MNs1;#&@wv9E%W)#dXcOrf(xCbWWocpS~=w)S<NF;Bx@EH`unk;f7qgd%zSW*7@a<4syxqE-dfA)KA#is{yx>#=`RWI"
    "fR`R!)N_!acCI?=QjK}kvGzmoEO@DmCx&Vxyv&K}41VTHYJ*CQ7B+KP@R4Z4WZ*VPj~0>F(FD@pZuBaS!e87meyL5+uDsFh^`1_="
    "C)_smB98Gcc1e%%vOlqt+I!evg}^yBr0#{{=#C4XLz%%XP0lE)p<IaRi1NlH=P61XqM0GwIwiqUWs;Skj20r;h-h|J_xFAr5-68H"
    ")72GepMO@Yt&Vf({)t;sUM0z2ZVPnpk*uD*UxK|ehL1XJPzrW_(qOYY?WYW=(2T?g%%;GSv@{Z)bLU0EkjlM4b0BzYf^^gabD*^}"
    "3WQUPCP`C&%Aj`$ULHy7!&e7!v@X^iiq>tkVo2+hTtwxDQOyYzi4aiE=c~dc!V3uV5P053gbXRgEcad{{8EDt!S^{Q&&v-#988vr"
    ">2i_9`@O@*>yvv~OSs(mzawkfUM#i3vCbfXL+wVB+nY<K)9kZgz62pvYiy8JFRVCUGIBrMO@2Rh*Hy9Wy4ZDHtP@_^-=hNwS1hG2"
    "akR;dPH2IF!oQM70zx~C14|Affut-XwB&410Kk(7L|fn?UaeAlRM2|#d9S#yJDJzx95vQ;B<oK|PJ<tQ`td!I)i1w)`1|k3S-<}H"
    ";r-Q`l4_!={+zm&7v7+-)-o65sm&*EswZ!172&4doOm~Nv&^*{xLj{rOup1PScWN||I9v}s`$ofrOISzhHiD>X})@}<d$mepv>dN"
    "K-$S0!9-KV<^p<@E2bH-Jjz&Go#-Vev&t+}ckYy`H#?lK->Ft|$@dTAG7^JHO8Y3V-~iD$S=3lxcNh8j<9PCUyj6QP2=CqOW4ZPY"
    "CuJEHID@B;`%!OqWQTiIuw&-UPd&-IrO->TZfU4JMW0WMM<t`wF*r`pfO0W1ueA`7DXS#|$%s;@EAl8&Ck!%B#v&1%CZ@{i&{>|2"
    "Sd(n=|HhLT7g-vPXVvmT2RXHr`09*$VS+oV>K@x2VH;J60Han^*FSfO=emglX&54!Y)Np2cr{itZ7dpXL4X%L2Bq+m17RieGBQb>"
    "O4evA(f%Vk`pY2s`MOj6ntSnG|MvBf-I+Gfi|wxf?ZbxB3m8aG8Ad@HDLHrwDI`y=LX3xq#t-ERWiU<!7-w}9%qM}k4%Yi1DUCVD"
    "3ODN27)FN-qTUed4WZr;dJ~MAn`q_J@?)25S{i8OQi@zjn2-wphbE154p2o>(HSkhiyT?hvn0Kb4wWaZQ@)eMC}ES+L@RszKGK<H"
    "PU-$$hAh9lHM8dObk!S5UlaSQ?8rIkMjHpLQpx5*U2?%zZw}o1VQo?ZqHtb$M~Q+Y17U$1qz5al)PzZ=lMTj1qbX;ED&e`NBuXYb"
    "=Y*}-*vk!DC3@FKkLU{`y1C1)70pe7PLbR+a$t8mIE7$!gc&cRr^-;l68Cx6+slNgRRqO2m6XVsGIk*)q7>5}2<Yxn+`Phm1UJ9-"
    "626!4ubB@DIB*DHHf@*ixzKe}s7qeh>P>s#FGKOp@DIm@AVen4AW}w^*Pbw+)8O$)lTrvvkVFt^h!EOxa5hA3I_HM1*VxMsTP1o4"
    "-y`~xhz>BE9#+}wGM#Jen|*0N_%4*OQZZ^$&NZD6iseiB0(TP7jt|Ki(D`JmkIX^}sISLhl3+FmzcF|LIIrKL1<mUMJ(zniUk=P="
    "*RB=D)vsLwxN4z2O`%qV<a>=l2?IH!6_GwMW|SbDOO0l>3Ora#gXStklZ-P=7{?5g!iHC}O<BF=UT9Z8eRWVLHyq{T95DU_qsbJS"
    "Oc9T6%)%x0ur8G*v&vUq?Nu}i_{|@0hh){ys?qr(htTHlV!!)Rc3(DYt`FP{k&C}Hb2f!pzUeA&x)1K$4A;rl^4S>=G^U5+?U?8T"
    "OYr8a?);ql=DpDBNND|gn2(mtr`WSr(S>EMn=)Mru+6@-JDY5<1T;~^Dd3J8q4FJ11Z_p&T!HWgA`hCNY8qvTPN5F!7>~losFmtm"
    "1KoU!y<%#!K(B%JV7>sDvr&V8g*!LCJ&;DNDt6rz>jcX?T{*BFY!VfobLWjkFej!h_X)pcf@+n7CyHCe6b(dk>$$YdIfg1}PPr=I"
    "(6PdO*&0^EiJjjE#(ZWo>$|9ExN+PW^qX^P+;@)pgo-wfNgeY-Jq28x0+487b-1gY0&=m{vB-`nV7n^^Lf|>k)(9V{_feuqN0T&="
    "=t9ilAWjlW5_M7Ie=<tYDDgGnCVJprLVqgqyi<`8jf01rYyeU{Rn2|M^ZKrXBhMfX$K_~c<_xqQ?x#EU-AkOQJnk6ek(E`0k@>W_"
    "ys1tKv1+0jpkk~K@24ZkX=1bCcw)b|A+kCPy0X{urNe{iWHbyzIJVB(o*GRiAD7drh573C;tayV@y|*^(Vrc?G;P-zI}WFWsI$g("
    "m=0pA8|_!%8ELJG1bB>&vIs!|(U1}{cq9^x)A=|%3xQh^JX&5tibyHRTrQ;VQ$h4fPZ#K^nD0saG{w3^P}4@c(i0sIR>>eaf`T#Q"
    "MDmfPWW1C<dpGjE)Y3R6Sz;s+DS_p?<0Ny!C-OG!o<n!uul(7Y?#Y`IpT31f$&-gt@a`ev8<dRDSTwo&tPW+|tYi76?qM`>yYA|v"
    "GtkZ;-x@U^c$^<MyPX%EVmWRyJ&cC;!^Kyz(jG0>+_5|~)v`T5J^!aHo|{TndHGAK?SqxV7YNJ6qf6y#hQl#)pHN#Z4kkaEgpc$3"
    "iJcX2T9WYl;TN2ROxM-S;85bfYK3Vr8AN2dRToxf%&`mZ=2@v6cjoPk898aZ`wZu=L5fw1dtQ)jF`pZ<tQ5Y^g*%S_+}o}8qjHi`"
    "R0KUhRDyxGf)b@QmC{9Jtx1$X($;b<EGL3naF!CAv@j)H<O#X9u^4VPWZa_^dyfR(Z@>Kh>kseqWywFk|KY<gzg|^R;8nT%+LH_3"
    "4{<sWf_Wn>=Li~s!*Mw+LE*vthG%R)-n(hT6?x>!`ly+|nzW-jx2F@Up9g?r`Ler(f8Mn)r?V`j^J-s-pm%QZu2K9mmsPc3m2Nhh"
    "d`9-db&yG_1WMpCdrQ1jTnEQ+QYqLuAC*?xZ($IMh>#pH33Y74KnIqTw?MU`((p(K*TxGOC6AC4Pnw{u>KXCIDFfdm7rlgj+fGs|"
    "|5VOmIvM5L8$JzPd2lwFWM5-_5$iL#?^*7z%h6a_#5IRh@7>c@7qnH$rK5<eF4{SD)$O#$=>@I4bCHvvsp8B)WR@wDb72RjQ!)aK"
    "34|w^H$y}uf+!a(iJmZHRZm{~$?FbA)0LyWYP-1ctDvnsX{S-k>4~S$RMAee#N#BCA9G|I4sFGrwQakps+D-Z{2Qus=eL$O8wQIz"
    "tpE0|wy5j2>X)rrd&a$gv*GP<jQ036ra{9{J8f*d*7*(1kX=7ztX6OFuO)t&!{GJ|UD=#@+P87Axw@*n{edMum(--6aJq)$khu+)"
    "_@LOhgJB%xN}h6f9BeH6FzWZ(>!K<0dpKWt2S)HloHoZu=Z*Nyx=4k_JNKzvBIoY?@OJ4Il^He<v*Gm7Ch6s^sAtw*KT^$ZmYelT"
    "+v;_ZWrY?WT|Koa`!>oIa)msfF6$BX3sl>oZW)JF*)DagSK<Wg(t3Srih4Ei(rV&-U*eR#TH?IJEGmyX)NbH<2TCR3knBiK9S(W3"
    "h(+rqm&$==T7j0-dmn>>plkpeg=7|ti!t=hw$qKp=h=WgXfF!d$tdf#C_|qFZ7F%3OLhv{b%)xMohaco4_a!*td*P*uA_>C%4jqs"
    "s~n4<4VrvO1e#A>xkz-<j&m=Jv8RW-H9B}XcY>0)6|ld3`1SW6KK%ac`?nGN_9E)oYE<`y%~xlL##w)yW_S+9khS{}IMjxnpHD_P"
    "{tJJ)n_pc(O*q)4K2YoO%rjr!-@Dnvk?hlyegOt*nre^XO3_%<7CiODKn&IspHI#>0y$xAN`eu`8TB#esSQfg;GDL|LrMrqLeD}c"
    "vQURS(c`^yyjN6w2X3@@(v4ioUe{&2#QIjJ+Kq%5IiY9;P$rp@5Dn!t#Ylv;mU<Vp2F5b%MbchS<)j8QAFz<s4E(ofB%Gl+?D$E-"
    "WI4{;RRtyUdXkFAswBt1oUpH+`<z(=viD^%xi6;@XOIy8cfHMVVJ1NBFmFK~V|3I-JGVMEyVRbZK2at_&;XJ|Nm1@63o5ASRUnaA"
    ">zECOT9q@kMWGzgfum^>P}mF3MKAE*q}lQ8s(0@%o8@Cwy)E+xVzk<&{1lrt#kyp&rj1q>Q-QHybHX?+EtROE0MpJIYC?!4a89)$"
    "`KmIV?;XwC=Tv6LC#58qn0n_)Z?=3}&~7&Vo<?_m>+UYadfcIQ*90L#<wL>50gpzYg5n9Ko=B01b4nXVqBlt?r_inm-Vl<cR{8c+"
    "ZiGAjXv`T#%IiBc^IC0{{(wM7pl-r-o`Q5P*SYPn>P&ke8{ueV5J8PjM$4oeFk_hr#B0V4h<x(jT5YxD1i0o1Z~|H@>U9)a_9FXO"
    "CRpDpRHn3vf_a<~uAHEIs7ejzgM73A4UQU!i-+^0b4rLwIl;fNJl09&25YRJ-^R|utKQ-kADPYvlM<6NaOYVyDXle`;k-U<@kh43"
    "o>~x>iFoPtxEG=P<Dyea$?l_5HagU9s~JxnPdp|9G<d;`k(7t*VulpCW8V7gS^_PYSDGcxnIVZgry0?nf6LJ+Zan{-Q-jW2S{#)z"
    "W$S@`0d)x=dKW$(Q(05?wCLsb`gWgroo7P+_+syvmGs2gxI`@G`LUAyR>dWy2Fk!G<apbW8$Rg(D21<^!d=Ra?QR{oPDV>brDm2I"
    "v=5RKj0<T3BTOZusBxfJ&YHoU@yrX6H#nlCOcD|SXm2<4uD)+bMXa}r%1MYPv0f#@smgW=_03MTdk8EKi9w=~i%67kRwV7B6r2W="
    "s5B&KWuoViQ45e%bommgkOG%P^3)@}NBXyf^o3h2=TBn1D%B~vt0vlU?KmS4JZCg{&js3aHh{D|X(lB8UyLdQt|F(-P^u}h(j*N;"
    ";%81se>~xm#}j(p`WYbHItYhr!i^@kI|#&2YY;X?E(pK9U1-0d33Xu=A~#eg<*c#9TGWm$M?gv^m9>F^wkB~ZEk*5FhMXmzCd#$4"
    "z|O;7y(Ltg?5h&xzang%c5g~G!etw*J~Mug_R3&28fV|gQZlHP%R$zcVhr5v4C*|s8*bZtJHV;g=bDZe-#`u}%B!i$4qm0}SdPnC"
    "_jBvb;F_0nvbFai*IicWX*Z>8k6C>?N*R~a>RC<5%I~ngbETZaFDLY$ebfDE$5$_N+kMZ!d-->D8ukza=R((|P*)th?nWyMCnLR%"
    "Xx$jAj1Src>#1}^P?a2spd6%3(aJJPgK`GHB?kXR0yUbao`p|g;S<t-Y%yVzR;|h>FkVmb&5Ps~c`X$A5;*~mY-5#yb^T<WiJ{r*"
    "TqRAKE@xH4dG_kYUjf_qr}tk}8kD%QC&fWks#AGTHPIf0Z@~(0ocAUXA*p9c;onXW?;=k$aqz)w5E=}p3}uC71}p`UZ)@c4%EkNP"
    "xb7MfdZkB}rCo~zH=1w7xa|=JuP=t}>AMme6gQbLn~HPdk9Fu;^J^NyXq(WEZ(%xG-lBwQ9+(#JmrJhZcWw&jtNjh9;dIP0o97cd"
    "^X+JyuVGW1)XsX1@4G&-s^f7^?&6WCgHN)&*{pG$Owg6_n7W$oeRY-RLsR#KZjOBQw^F7hc4#!2Ov^5JwS^m-UY}A?^P*c<e;)I`"
    ")f5fJNFteJHj;|1^`wen$^_-d29wm%#V3^}H>}&8*UDWTG?0PU$g9=bj`fl#PHGsVauML{{Ooy>iX}VwoMlv5$eUz-ZoQ3YpVv0{"
    "MqtFtrIJ6R@_KsLV_lTt_3(Ucb@<%7RiC41zu0xEEi8HZt*eKT{0h7peU$fpm3CdUq>g;7&2D@u1um<|?l#|kpj?7fCP?6cBnn=I"
    "<hfG88Uvmth*p9(oKs0j3`&TII;|$28L73PXS$Z_&8FAp%~)-?G#Ni@E*_NA*JGG(@>g~7NZyM?l;vX-yMumnX3gs|g|6rI)?6X+"
    "Rq>O%-P@?o19aY;+Zg^wc+S6HuYbQRoOc>;KW)XCa*;`r@Lx;{#jID<X=SBM`SLEw&^9GX<t-zxoh1l;Wg)T<X_Ed;qPgYXoXutj"
    "F2?zQvK^gqUR@p!<Gj-2&6#yi3KsGA%{uFt+ITKWtiEcr1DyYSbK+={&B8|~63(l72Ghw53l-|XcgzgbSmin7Zy1J)mYXY1Y^O}<"
    "yv__<LTsO3YhI~jP^yc=#kuuO5t0iu18e0O>g};?gV!O!;corhi*x>=%Y}Nm@Dg&t59W}2vPUHN>-wh)OM_LD2d?1_JPDzMM>UQi"
    "^(xfu49(I&Gp~SHXH`s!aiEs?<Sk1AqR|?RN{Z}@!mGTIyFSTv9A1fL$G+vuPe*`ORV5KtzxN06PP*N0O=J-k#iVbjx7r-RSN$r^"
    "xeGd!>b0GhSYBZpRW&Po?Xf8J<|f?!*n~rs6xus<pYbsiozLTC6+b6%_Yc``aPZtjeFxzq&vcHzeAw`s<ntdT*|{5(wOK!S?#aI+"
    "-5RIdc6YKj<HC-LjhQ`p?oOMcKC<;$q7WG{-xv@Aj(u99L|cyc7)rU+^}5t`DRo%^xwj+jx7<-{Omv*k09;Fye<%x03X+1PURp;q"
    "OG&9@0hEb>I^r$i#tRjEBnMm|kM{32Ev5d}<K9t-Yqe0=z94Y?guitV`n}y~yJwIRVWmojNXLXCoNC8VVGI_C_e_f<bnp<VGFgq("
    "0{>P)pblw)kr3aOFX2h;sy5gflR4j3GN0yx#b|D}iy!Z0S2a&&w<s@{*mIQcDDOA*%C(F}c|NNyEm>7KoNqpR%8uerhwFlSJNV@0"
    "P+eD}pjJ6(vR(Ia{+tc7oi6Sc-{05O-o_ABpfLjc0Sk^duZ3xB>xi_r7?wDvqLh^lzP(<aaw0iDcMI(!xK--r_;cX9)jW0hyT#|U"
    "#`L<Xy|Hg~HQDk;D+1L>oTc_L-z>GSnh0Sy&+mN?_mf#WAa=?fcdC7-jzdS;v(`02y)IL1YXzHy_Eqx4JG6Iwk|o{74OjVN<2FJy"
    "WLoV<qdkJ-83zFgC*S|%Mn}|D$g?_TTUG1bEXT@}+s)T|r+aH!yVJHdUN_uWl|KeSd-U^_m9p&;%N$ol_qhcMH@|E<!H+g)qt2s!"
    "wkMtj8E#(1q?aJ~d>vccj6VuA+?lQV_x&ct{iKR;Dc1zH)lmPwirHu}JnMsz86t21*t-SySN3TLpAS@#e|`h5%+s<v?2N*p3>3#+"
    "Y!*@IhgHo*UaW6QD^XV2Z_&6+R$hp+?og}RKxHI+9Be6HgJl*zbyso#%cFh6OS=`$&ZV@==Joc)RmVPsy_(TEVH8KY91iOb$LIz("
    "XQu5q#*x1(vX7I;XCw*P5vB)4<slLFv`{%pNE~MWqX_;;=03>D&+<N<n}6k`i|rn<Lzfx8`fZ>MGrne^Jz2f*Q}yG;6M5}4+iJ-Z"
    "L75IBXIc)@YR|pp)M}P25gwdJyFPLwsDQ+k$N!~#mjqa$6EUFpx4s$lQZBOIm;4A%dBL^fsr=Xpo=VN_=RO?cBnd?{5r#;kw6sET"
    "O9-PT0t5rrQ839Rg&)BK1tz1hjD@7V?D5p&=_}zWtMRRPDnE9Dr&4n(o}}iCG0j{|(GU?dW5zqGvUqYaa49KKB!EyJxYP*&<zvo&"
    "fEe@Ih8|Bno?aSH|60NlS~qUWuib3jY&G1zrx^%AKvCf|^_Izi*s?Cl7*G>TPI&?`2`xMe3b^7N|K$lG+)ELtF@Nkm%`-h$n?t)g"
    ">QeSHUL@SQ-yz)(HC!~=b5lpQ>_J;q;CfZyvVhxd{=iWR!zopiN2U^&N(dsO^AVI4(kdx91Q8?0A042!D5-_0DMFG7rEL5rF}E|i"
    "_&MV8gM3_VFm(^3iHkk<z9ROrnzY}kQEsH@z@@QnvR%4G)CqOsDQXsZpjL+%DIqaQ<)xB_#3-!O#t;&m1hmkiR16>jHNyHny7jR`"
    "c$gD>&o;K6?k4wjrtZ9RQ*AUpzD41jt;Q$Xf4cf!cYQvn%go}d!fe_G?p)-$DbfMRx4O^{c2r3%&H_;IOa)X}1+jt$GzNw7o?2?X"
    "QN{oS6tRYbu#{=RDFG@2^}Ti2TZdl{VR@tv!K?h<6}C#{?N@pTrX7fsoXFS1TAyS9A*>9-bIola%qC`}51ulrQP`#=nM1{va;>fC"
    "rRWh-G{*rBHq`lN#KCV=-ox|x@T~TJTd-OG*a0x>np;uH6qU|#?lmy)D0P6aqlqxeJ&HHyC3qcKu$%^|w31GuAxVfZj1g^FkIEAQ"
    "i<(KP71T*it%VjRjE}CUN8$yLxOY>c!r|q&B-Tx~tDJ}_p;VySrl6!%CIZg^@WJsIEhRoDV3vYLqL@I$CaSekSUeiZX^+8YO2%H`"
    "T@q&H^kfxeIC+#;u{5{-@q$nr+`Er3zy&spLstbQUjNUMo?!mJuD8EG5V|5sB+&trT6jt*WlEIYKoh+n+y$mdG9q$GO+q*lt&Pq*"
    "^C_6*<+rufzWL-$_2f-$?A_FntnaErqx;ZS>!Nv_hUM5XC0{o0ZQEQ#`5bH&(R(+{sTx-|iR7`nd2Z!30COXQ<#;h$j?3^4=Jz>7"
    "7R%inMKJd+Y%jAqM7<fqRodCj>Q)cziNvq(x~dY@-8b)3hg8==)Q=MSZdF*y@43TyX8@WUZa8`Q<Tupu|0h>lofp`tyqYomGv+|>"
    "d@pp<%IWo&^GK6fm6bAITvx^cbzEo~$Y;y*xIEp+Vt5ae<zg#tI!lv5O*++fTq;L9n-Ip>JXK{A%mA9zN7+$cO!Jj>pWuYWesjEM"
    "a_>SpeguyghF<2KFY~5u;AV?qayf-S8J``wH+9!df$O@!1!do!=G&vmP-<~QxVIu_S2G+epvIY;P@YN&1Q@XBr3w!1LS}<>(c6?P"
    "6_V)iRL-W2UBgwER)-T;*XjK9(=Y!ReE;i*AOG_G4<82K|Nh~>e);tk?=0>N?#7No`CPGZ$%hnuN!)OAN+sLLaM#%vT9dW6)>Nm&"
    "DEM9PS$3Bw^SH6<vq63}E?S*)yM@I8Mp_-5$;CS2rLC^CvXfPmfM66XRY|HCq)I*+7BqE68>%JKN^|a&!w*3OV}Rw{3D&rLGW=QW"
    ")aOa)A@m4B`OwRxO4>J_jvfx6XjSsMD%lZ`c01IHrRcddXvPLfQdAK_6b8_w)m%gJ#E=w{kJ?6tKS)FiTCiMc5=;z46LPg9iXMIb"
    "BjW1BtXSI_m`_W9wNA#qm6KrxC3vXG(EgH1wGP+49OHtTA*sZTHI^f#aw>$$d|!24<dNtsm3Mu7Z5VSZD_mPUXUtt)RnC#VEavtw"
    "&eyhaUf0__eRLeIq1DpijdRee!SqPWBUt6FC?^i9F~{-4ehoL0uGO8Gzf{(*uXCLCxJz*M%-l&6(Ro^~UWy(qMRNq^aQc)+x|XGN"
    "`7Tw{{he#S9@8hzvP5NulPI($I&v$rX!VK(W+6!Hg675>O*kY*s11P#5)GixeKR`hAynlar|i;R&L3qccs$-2*^}uqFa3EQe4Mh="
    "YwvN}C2kuTc@$_@g*!*=s-<={SaKtTPL9&(qv77FNGNDfK81j$qmhYoieFm86IGH@12H<TT+YS!CgIwN@_JU%mg2H1dTdE)QAhsH"
    "U&v>5q$+c6@`c{Z^-?4?oy<|gEJHMVf}%>%>!xUT1hw6zR(jH)DYubF;Sw{+*rW_qmTHqM=xC|qM8s$e6GZc<2m`0I){5n8UybcO"
    "UOk*Tg42^KdIhC!HS={>+E2oPRU#@GtusF4pbhO%%By^qn-GhTA(UD#tpULWLuqevvU+8ij**7mY1~7oD+uj5%eEIomp<6m-kEki"
    "IXMjmD55BEPnmO62$VbcnNv=MiAgD9jOB!)`O9QTQWzg2H<lO`dldC3>Ig;oiM7pl44(26YkRbFWbJgYT~b9#WU$I|?S;;EXw3Je"
    "FrmCxlyNFqLKBn+%U$xCQ5`HnjWD5ph#DV#leXw7DMfe8#C;bDANH7I10|7PeO<(+pZ@M)I$7KyOv{y4Wirt|oj?_-zXI;YJYV#B"
    "h<!clS*1f(sS+(7!zOjfu34mRrky=3fUr#3L^)9a1m{C|qCB-C`>LWLhHD~~PRwzTRzR?Zc!&CK2$5Ztw1<-t<yh_DZi1=zX|?;b"
    "zPjtF_awbMH_YK!ZkWT1aKrqN8_CI#m4sk`)2KvBG6ZI0&J3uSmpcE%!Ft1kP(X<?K|8{DkR&Ls-Z(dO9`@J+^ko5BR_8JJtO|Aw"
    "&#IMHbc$pHifPJaP#_Ffk(Emj5qb%&0E8t?)Cn$((as4p4XpCUX$GKmRH~QUz2xqRVGl8^LlRfZeXrMgRc_4?mv>vYbf!I!L@;d<"
    "Wl9>xQcPTH=bcVDg<^6>NNx#D0R#)mO6{1&FSxc@!<Rwx-s9Gzs4EohcU<p*Q3syuw(cCrIB#eq&Ll2@aSxuOp6jS46j5UWu!z5^"
    "6oD4e8nkj~7=xz5=YzbY5AkRhsz=t@qw!*Btdm&hye(K`jv%-n?!jW6MY}F`T^GA768Cqd6^E31NYQ&IO$^!Ow234dz2weHp@~+3"
    "60boB#(AJFIRac$AOb)^lIN(obr)OC82<3nkMDo}F!<&74}bst!{8sk{`ld2Z=UvAXt#*X#h=7$Dby)iOAGDJWEQD0j0j~2V-9>U"
    "HYdCf$x>8Bc}kWf5gkZNED#%wM{AXMgfy0O@_3o~2%){|*+XXsI;ipm7`1|?{<#yl)OEM#Ez~qx9UwXc1w=H+q$9!#DUI<~coV6l"
    ")M{-JPnyy|O`sA2;T&?DUN6*oq4q~c=3(`-OSSVUbyEvzjY!H^;v`YPC`hA-;7SJy35`GL5uzamTCnJuqMTUcQ?y{D`DT&%#8usE"
    "!?3miS2xmrc6)Ba+&U~+?sB}H?Sxir;=7zo&8-h6X=O)#zJu}Vmd_VG4!Y-1(WB#(w=jn4l~#rF$<PF|jGKHIchn4LX??Sq?a^69"
    "gA8t$ZWbRO?5&bMg*!LCg_6>&TxdIjt1~VkePV9TKZtp7%uadvo~|!V*Zci;9o-1I(`@_pS8$R!qJ%{&UqupA&`yWIkeRI|iYO%l"
    "bCJo!oul|$^g;#3(69iBB>OgOjqWJ8y`oJ{T#lQm%rY)BZgb!AS){(ncsqf3^-s;w>T<98WLC%Sy|4u7@=oiMj=eUM1Ph0Y#TCrV"
    "2OiP{Wz{V#R@Z<JW5;ZN+C{#{y<|`OUz7F^Cwi*szr!?7`?}F84xDm^Qw}5q&!h#WHTU@hu7JRkFvc3GLv%LZ!{I2g5&-`r%q1Tg"
    "wY@ml5(h_B)I;v#kgIvT9d1p5ZlKoG-k#}^Ndd<2d<CPBT==X?2@(_n&*q~&&JZS)Huy)7XdDx+6{XS#raYMR_F#67xJJ33#Ud0<"
    "U?sbo2cN49Gzl=OjJB&5mvd}y)mWbp<F#P^z%5p5+;?@4RZBNo@y}J1-Vtpr3RNnYi1}t#k)%&a5J31#w6=sqTMJOQ3TC)8DJH@l"
    "x3=Hm>7jF3=p4xVv_ei-xt{iP;=pCb%F)0<qK=CCsSGmGl(^+oC@O#}Lp*1JOJ_t>A<E!M&{)h_$k!nExao0oIoz}ay4Q&5BD#I6"
    ";dUdAIc8NLTnHb%)FMivL4ZbqLePRU5gb=k6a1&84AH}tWr9j6qcqlktD7(D;Knj7jr*#)DC1G$(TA$ka6ZUcAxF?0LtUKY1Y9kN"
    "RftF)1XMBoZ1NFT0rqB;{bqG9ZoY=2ve^J>=D7I#=8GX#zc-iZs;(*ou|74M18Z87Ol?*@|9URZqwXkKPg&J1v;``wplmkP?_7HD"
    "m3GTs#EW{-ow(U@oNv1rxJCZBGqdmo!m`S$y#9F*ma|!&q~ctje0*kYWg~CkN0abz<6QU|n}zk*Ki(zmVB_(ODrazCvIy73_wHdn"
    "MT48o*0;3}VEhS2xtII>)F(K~TdCvuJE$jI^>XTF>zQ8q{pI(s-`<P=HFdpz52v`o=2PratHy_AuA4HQ=zW`=Xg|8d!8<2C3zSg+"
    "a7p9~WDEmF2<n62f^%AN5=;Qa5>N}8Gf<IIFD3LgQjePp;HD<M;-GzunCjQ->etI+Wvk%>DYZP)G6=9C7&MeP7)^raXemkQlhHg9"
    ";S*KL>fo)iV4@6C<fFe<c-VKH;69M7FB9D87Y<uvAN~E;U;g&@5BS&nzx?#$U;pdF(eQcIcYStYNgY{dp7GU>!*K!KyczXk0j-RK"
    "E&XmKO{-yeRB!beXJAn-9cTt3-v%%r#Mv+{PSf^R%VyQLwZ31>qhhCgH9f!SRLD2yA=buW^LW~>);Gt&TOb|gY{84W`S~@kX5kJ-"
    ")5p{I$Z$BV_H77m+lmhZ7e5W>li4%IWxL|x+DIw0Fn0HQGhnUOX1S9xOlH&Nrd7D{ZMC@b+L{6K??Wd>&$*^RD}Y{JzurGd#}EBi"
    "SH}C>8}};`xR9~<aC}&yxNb^yr&z2y(ym}Q2*P^BZ4yT3I~omY7B)&$vmuat(-T)*yU4(r96sZ%aZ$S*3?R6(y@K()6D${yuiv($"
    "y1D>u@9#rTh|eO#ISQBJ0d>=S^YQ*|+q%$oU8sY7+kM?=WkZ&8rGW9sbxu0&AlitQ7WLWpK!g@b=0vMZGUjO13@xq{6J^8#BSJu*"
    "UG<3UswY?8yE{4qWy{|1E-bs)B;MbZ_7fmBaG&z2JjI0!LTMV9Gd$Adg+d*L2}v!nM%h4&q(bC`EjkLS5)GVw3klGkcN68|r}Oaw"
    "S2pzqcMoyqs(3~$TH8DsKx=Jd>K;ZDcjEPt%}Qw8EPj&l9tZxRNaku&@h#k;+2N&^fABrw%4(^Av8@IIzBTGY11RF5Y6d_1tQ8{O"
    "CinMH7RzeWY8YS5<&+)n=<N(xFDfr4DmTe(ukM-)Tvr7;&|7z#KM<r(oU<}S!%Q~KJ&BAv2Sktn3AnV1S)qwEJ_!6oqjAhDr<fy#"
    "#L!#tFJZxVmwlqQId?F-$H$2^hL0@>Ude&A$x#*W0MD&mYtK-j0CimM2m$XHrJN-L%qs1ZXCYb;E+qjV6MjInqrM9fv_%?VpvW2M"
    "UiHz%`{B4jcO4q};g?^28vO11pMU(z``_LQ!jDjXH%}!FM$SVy3yu0&aTgWa7N*!E$cjK2hvy`V*t1IV?2H#1=ZJO}&^fBkF<t5j"
    ">4JpRu10itu=a5mTFE9wAC%Ax^@Auqh3xD%Hh^>?U)|-1qg3Zh@w5zRiL+o*WRy^CjU-8^o@`zT*?eU)b5)U_Ocr?<r-Qot^J0Z#"
    "{fL(P=_HfdGpw}dnO{A%U69%ue@cDp)l)QA7r$<bcS(7>U2D(NN2yUdqEe-$3L+q-c_%GeQj+j|RK>6mh!HV)g@#iQ!bO#7&<P)+"
    "a94%I>OOvgt94jHyN~f(r^1(Z-94&h2LCLPQVGc<lj{_h$*29K_eO4l=t=A;5^LEN*-v3z?2R1iR{N<_5uM=RSqzq<LMHNNrVuPp"
    "P9%>m8r0vk_c}5bJ!Of9NFq-`D#|2-UHW=*f8^WcuBW0fw`MHIi57zma^zwC#1PT?<>u@v=gSZPB63X1YiRR5Z+eb}tCIu%dLn*Z"
    "M4a!jY)ON@OT)Qn7s=4uyVQPtfgs*G&o!f9loY`kX<15WC?~~(b3TZCf<;lSt>-~=oxm9CLsFTadjtASMx*pVZv%SyltUArf_eE="
    "3U&$db$8lt3JRdmB8-vvWE0cTd7%u|+z=p1*_8j{j7w>)q`@N_;J<`b#t9P*?IHeE&%yOjY=h#;`G16$x+&YayLzirt(eStb3*dk"
    "sUQiJ#MvM;0|DHCiIgxMgo-&Sq){R=V4NUgL()`fL^A6!*<<oGVY0D7j@!VlOTWbabz8^Uca)eVj8el9W}Zbrjn^lRAOwwiv6uLt"
    "v)QX^8Df(Q6sRhBYw=%3GNt<9l&^lgq`Q6U%iS2zlg{NxXU|E(Cy1wh;(GIm4#{U<2ipk<O>yG9rA9?*Kq*}B+7h1cb;(!P8{sHY"
    "4O-()6SUV+XV)MC<CG_rwCD-wr3vWZ3E|Ci!HBzQ)=+ZI<2b+tJw2<QjkQ?rHOK+QbzevBVLNT^k({-^?VhEc#ZsU03zd`mI9v0{"
    "=+mApno{OEm$`1rT$YLUbfW!itul#f3tq>Rf}#XGB&}R_3?Kn{s(2(cL?ForO`@=#qPj##0zrW8^#&$4njavas(Y1DQjV&uetEOI"
    "#E)kr?>m%J4P*F>lQ$iV;1i6xyN0+2=^CVK<qX1b+H&f1<vyqib>KzV*Nt|Z8libIDrhH!vXls#qz*i)M2KUN=_nl|5Wt!cOpuXB"
    "PMtS8NKF~*b%Z{G{!QSwOhoqZ>_E2Uqc7iI5Tzxr;{cc6Fb-X%g<b#8(IlXN`(M}F-yg^!jN&vnW2_Y_GG>MFN^+qgfmJd_8VOgz"
    "IO2(jiirS%dhe}QPA5)vyNIp++y~y-B%{v{GQCui<qslhx1t29CvR$(-c5a^@m;k$z9TD}2uk=eoy_wIO+OpP+l@rI<4KXVGxs@X"
    "tj%eBR)V!W^XL%d8ok5uC#-rhd%%T<qqnZJq}+`gnI5VXK>JhSt`9bj-KV{ElnkN|^*8&f$ipxn%sy}27=}V*O-`H7tX5}!&^zqa"
    "cr&>w)-;$Swd516P2!@Fo83bB>G+DKF%3S?+;ocg$>AAs626oU!K}5CNhY?96vibfD~uB^Hn?xXU~xpSrJOe@uh6m)+FD^Lf9Ga-"
    "<TkxOrJ=!!GMe|i8%8Wyx{GToXCd1j?&In%G0BtJM)fFHa;Dz8`rPfk)&C30G$%j<1i&&^v6*kI{;EDnnsZj;s+cTip_-V|+R;n@"
    "gcW_vihW{99<gYiToT7mLu<)w)uN2vDY9?SdpUf*9G-*2*R3p@9Z_8URN1+&P8vr;8Q7>}G-%&yEd{rRMN5pxr$~ZwMktTkGqFAh"
    "Cpn|ud5}UI#VGf!iuA59UfH>Bn(s9#^0)eRQ~GX5-b$ucSpU;K+#@>wRIKE8>#@bfwmQOGg{a{pK6{v6fe^0e>+_s7jI`%UsGRL<"
    "7>3y<9xb7eWJbZP;!OWg4b08S^=_`m!QEs$nc-6|i=sJxGq0-6(S23C%<%%Qt{Cf?*6Av9g;{K#DURw2YkIh}G^%S~Wzni@udd#j"
    "qUCY~Z#HjU8A^@waj~3@aRgoYB?mDsvnR5Cs&v0Byjh)HA`e*3RrLvuZ?UPYN}y2M#ifC7g^%2hC-cQHoUr1aBahAzH)n{GzvfK;"
    "!;ls0#vSk-{)BIW04{6!T}>bvvI{pH<M&1C;7Z=fhk!HCo&e#GDP(F2#RXlmbs{+S#amVm)w<MmE_Lxx%gY#oUb09MGlZ!mC=*IL"
    "8?Cn{x$JkfkaH#{4Fo_dmPkm>`G|iSCkQ!kRoOQ$doFHX)GBugfp544DHiKM^xzMBD0q9Zx)5NxsIvIh1AeydyI-R{rHef^bwo}1"
    "*u-c!{&;|wu*h{T@;XTgxQpJP28`;h%=<bz2;d3n$7<?>Ql3ypt!COQt@FN+5fDHqkzA&+V{(@Ds_~XDcvdG*pN!M+77gexc^k<1"
    "tt4a9l}l*09Ix(7&kAiZxG(NnIj6Tb7a+8rn7Sb*zZ`uWAP{f!Rz)i}<x<ymsn<zQ+6kjkagx$;Fu;L(ZM4nzs0SMX`2m%veABb#"
    "iCdv<(2}H>g7Z{L;d^@O>8YouS4U3)=XsIOFNJn;s>)nrnb%28K9#HsQCXMc^K>B8Cu&et3L#QSHIGplYjru;%z>%sCD#y>KwS!;"
    "r>35odTM%o)U>Rx-fSnPWpg*;tMoDjMTPgEwf8jSJG(8B$$G|u*MtSCSY(hKmx4*JffK1LeiKEI-dowz(o6Z9S}R;Hu%0PiF;n1D"
    "a^=ANzm_n2*h>{nk?X3+YvT&$A@O9RFhF8HaS)_qISW8UQz~*nRB%WhsINdG5~yT}I-W>mgap)ZdXMy1Vu&97UmyK>;GWu)stUd4"
    "J*i|EQ&uO!g(b!bC8;&uQXjdpig3<2GnP7y-+L{938#WelzU}D<h{1gb3xAq_~>vWsBSM6lrq=rGOsQ$N~VMY-vwuZc@>qV#&a&C"
    "_mVQ>xBw&tNKw0h#sU$6*aQ-kl~j63dR^c+{8#H>9S^m=bjp1vS!=8g8x;S6o6f&}C~f&3Cj^H1PzZzxmWWTj<jcl;_Vm^zy)7nB"
    "C_B}pFD9>8-BBjrLXfD{PNKbI2uP&~C)^sPLL|m2B(wwu3j{{c5b}{G<T?vRL~y;j)2ll@AHWxEJyc2EC*uLm*8O}xBUA;itAf{6"
    "!B@ABV_l$NxRk;9kc^kY0UAI)D543ACj9^Ho&9bjDGb2hr~-pAewxUD-HWbitA0qgZ+|dp((X3dUR&MntcoJ#kBo(8GVsGT{s_#j"
    "aCIaO&`J%y_~w%`OU_gA`Hv)MH+_Hju9N!fS+sA_XE#^>NBYp)cQ(DP>xWLCb)!=6X1wWfFFys(lkmk+cx~{h4ifkjv|<V5F;s_~"
    "y6t6Z5_46f{xN5%VQ8snz-(AGaB`BPpYWMS#}iR2LDXo5GjdBtwC`yyb%~2-iPZ($bt@=(R8;aQW5~u5O9t|R1#4C--XpjOb%YI@"
    "7SxzyiW$LYo(T${O^!QGjT7kuOYYjk$k5(bl6ilM+-}>a*!AV+@F)vr?qqwvl$}<&+b3K763o3fWoy!H6?9u1K$mxN``1~#EzY04"
    "$m$Ne6d9!ztDJN5+;yrXNFhMC@1h@NK9h^lDuz_3e?(pXLC{=8qdNIEeLi1#^*>&Z&8cr3KefFE1P+qxHM|fxlE^sEu28wdAW@0p"
    "u?Ykz$y#D6rK>&N_9{yYNkB?I0fZpa@cOi_^J+33b)JXq!%|G;Lv;XN54(TV!?25k=|}x(syP#M2hi>0_9WKE@2gARbh&kk)z*rd"
    "H=q%@!#)eu0urhtmkSgCYtUK%M0A{64J{8PXhQ5ad5_*X__1cnaj?z(!}jWG(_hu~_`A=$re1^+f0w4-XY;Y7$1(WeL!;dPy}dnM"
    "#ALzj%DrYY)cVhW^39v|KZeMf11(i5N#bhGryP9pL4-!*iP9{MnCjGGZP`-SKV8FMT)KG*kz&q~+>AV!R_NqFf93bOk4HKQf#v!>"
    "5NUM;Fwqo+6szV85-rdODQdnYN5K<z`_qVdw3&&aS#v1Gx;+}znfBE@m9@F<zv{YwI`kinDjvJ``?%Z5nK<jik^f%w;vl*@{}ZJI"
    "HK`@`P5Y+LO{$W0`%JY)Vu2P=kf>khG7jIs$fY_0ud$R#gL&{j@w5^=Ew5R3r*)F0GX1!?x{MDGjhaClwJJP0@+DKy>ZPKo#(-5Y"
    "QuSV4G?rF~UG!w#9?9b3M9@@7zVwP;o@F;0Xx*J(`7edmMu6;U^(n=W!4$oAEkvxUd0;3SyA|SFj!?P@0>+wxxCAgx%NwiHFbOaT"
    "@O23=I)1$2l-vug*ew~jxy0S7C}i3coGS(;jTY3P5xQDH)quQm2@b((94&A&CnBr}ZMr4TvEW0UspoS3UCa5YZhrYTd=0mH*B|M0"
    "c*|3Fi}LN_h2ZK6yHtvyU}Gw%E|*fhYHDb%xtRL)UO2~Qu7=T&3Sjh%%PGbv(dDSqyYSiQmQ&N|(3WC}=^eeIxBv9HvRQg{Eh@nb"
    "NttXq$)?4JIhu9tGviKk=^%9RB(ypvX;u!-TxcCVEgMu3ZEV=GP>MFp4fZ&43IbOO()E&*Ev4+#;mj`hlRchi2YjBk&x8Ij-8XW1"
    "+5eXj=W;BF@oPP(FK=>ka0MJ32GtuBTtrrvVHGSE^hO?~e*ssA854&lF>uKv^*}oMJfrzqY7QEl0CMCcCNp4fI$XZs>i-vP>dH?"
)


def _split(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.split(";") if item)


def _optional(value: str) -> str | None:
    return None if not value or value == "none" else value


def _bool(value: str) -> bool:
    if value not in {"true", "false"}:
        raise ValueError(f"invalid matrix boolean: {value!r}")
    return value == "true"


def _matrix_bytes() -> bytes:
    payload = zlib.decompress(base64.b85decode(_MATRIX_B85.encode("ascii")))
    digest = hashlib.sha256(payload).hexdigest()
    if digest != MATRIX_SHA256:
        raise RuntimeError(f"capability matrix identity mismatch: {digest}")
    return payload


def _definition(row: Mapping[str, str]) -> CapabilityDefinition:
    return CapabilityDefinition(
        registered_name=row["registered_name"],
        semantic_capability_id=row["semantic_capability_id"],
        capability_version=row["capability_version"],
        handler_module=row["handler_module"],
        handler_symbol=row["handler_symbol"],
        schema_provider=row["schema_provider"],
        authorization_class=Authorization(row["authorization_class"]),
        side_effect_class=SideEffect(row["side_effect_class"]),
        direct_exposure=_bool(row["direct_exposure"]),
        gateway_exposure=_bool(row["gateway_exposure"]),
        profile_membership=tuple(
            CapabilityProfile(item) for item in _split(row["profile_membership"])
        ),
        group=row["group"],
        feature_gate=_optional(row["feature_gate"]),
        lifecycle_status=Lifecycle(row["lifecycle_status"]),
        alias_status=row["alias_status"],
        alias_target=_optional(row["alias_target"]),
        deprecation_status=row["deprecation_status"],
        replacement=_optional(row["replacement"]),
        description_authority=row["description_authority"],
        result_bounds=row["result_bounds"],
        attestation_probes=_split(row["attestation_probes"]),
        exact_test_node_ids=_split(row["exact_test_node_ids"]),
        indirect_test_node_ids=_split(row["indirect_test_node_ids"]),
        compatibility_disposition=row["compatibility_disposition"],
        planning_rationale=row["planning_rationale"],
        source_evidence=_split(row["source_evidence"]),
    )


@lru_cache(maxsize=1)
def build_capability_registry() -> CapabilityRegistry:
    text = _matrix_bytes().decode("utf-8")
    definitions = tuple(
        sorted(
            (_definition(row) for row in csv.DictReader(io.StringIO(text))),
            key=lambda item: item.registered_name,
        )
    )
    registry = CapabilityRegistry(definitions)
    validate_registry(registry)
    return registry


def resolve_profile(name: str | CapabilityProfile | None = None) -> CapabilityProfile:
    if isinstance(name, CapabilityProfile):
        return name
    selected = (name if name is not None else os.environ.get(CAPABILITY_PROFILE_ENV, "")).strip()
    selected = selected or CapabilityProfile.FRONTIER_V1.value
    try:
        return CapabilityProfile(selected)
    except ValueError as exc:
        raise ValueError(f"invalid MCP capability profile: {selected!r}") from exc


def _gate_enabled(gate: str | None, environment: Mapping[str, bool] | None) -> bool:
    if gate is None:
        return True
    if environment is not None and gate in environment:
        return bool(environment[gate])
    value = os.environ.get(gate)
    return value is None or value.strip() != "0"


def definitions_for_profile(
    profile: str | CapabilityProfile,
    environment: Mapping[str, bool] | None = None,
) -> tuple[CapabilityDefinition, ...]:
    resolved = resolve_profile(profile)
    return tuple(
        item
        for item in build_capability_registry().definitions
        if resolved in item.profile_membership and _gate_enabled(item.feature_gate, environment)
    )


def gateway_names_for_profile(
    profile: str | CapabilityProfile,
    environment: Mapping[str, bool] | None = None,
) -> frozenset[str]:
    return frozenset(
        item.registered_name
        for item in definitions_for_profile(profile, environment)
        if item.gateway_exposure
    )


def validate_registry(registry: CapabilityRegistry) -> None:
    definitions = registry.definitions
    names = [item.registered_name for item in definitions]
    if names != sorted(names):
        raise ValueError("capability definitions must be sorted by registered name")
    if len(names) != len(set(names)):
        raise ValueError("duplicate registered capability name")
    by_name = {item.registered_name: item for item in definitions}
    semantic: dict[tuple[str, str], CapabilityDefinition] = {}
    for item in definitions:
        if not item.handler_module or not item.handler_symbol:
            raise ValueError(f"missing handler binding: {item.registered_name}")
        if not item.schema_sha256:
            raise ValueError(f"invalid schema provider: {item.registered_name}")
        if item.authorization_class is Authorization.PROHIBITED and (
            item.direct_exposure or item.gateway_exposure
        ):
            raise ValueError(f"prohibited capability exposed: {item.registered_name}")
        if (
            item.lifecycle_status is Lifecycle.INTERNAL
            and CapabilityProfile.FRONTIER_V1 in item.profile_membership
        ):
            raise ValueError(f"internal capability in frontier-v1: {item.registered_name}")
        if item.feature_gate is not None and not item.feature_gate.startswith("HB_MCP_"):
            raise ValueError(f"invalid feature gate: {item.registered_name}")
        if (
            item.lifecycle_status is Lifecycle.ACTIVE
            and CapabilityProfile.FRONTIER_V1 not in item.profile_membership
        ):
            raise ValueError(f"active capability missing frontier-v1: {item.registered_name}")
        if (
            item.lifecycle_status is Lifecycle.DEPRECATED_ALIAS
            and CapabilityProfile.FRONTIER_V1 in item.profile_membership
        ):
            raise ValueError(f"deprecated alias in frontier-v1: {item.registered_name}")
        identity = (item.semantic_capability_id, item.capability_version)
        prior = semantic.get(identity)
        if prior is not None and not (item.is_alias or prior.is_alias):
            raise ValueError(f"duplicate semantic capability identity: {identity}")
        semantic[identity] = item
        if item.is_alias:
            if not item.alias_target or item.alias_target not in by_name:
                raise ValueError(f"invalid alias target: {item.registered_name}")
            if item.lifecycle_status is not Lifecycle.DEPRECATED_ALIAS:
                raise ValueError(f"alias lifecycle mismatch: {item.registered_name}")
            if not item.replacement:
                raise ValueError(f"alias missing replacement metadata: {item.registered_name}")
    for item in definitions:
        seen: set[str] = set()
        current = item
        while current.is_alias:
            if current.registered_name in seen:
                raise ValueError(f"alias cycle: {item.registered_name}")
            seen.add(current.registered_name)
            current = by_name[current.alias_target or ""]
    if len(definitions) != 185:
        raise ValueError(f"expected 185 capability definitions, found {len(definitions)}")


__all__ = [
    "Authorization",
    "CapabilityDefinition",
    "CapabilityProfile",
    "CapabilityRegistry",
    "Exposure",
    "Lifecycle",
    "SideEffect",
    "build_capability_registry",
    "definitions_for_profile",
    "gateway_names_for_profile",
    "resolve_profile",
    "validate_registry",
]
