<script setup lang="ts">
import {MiuixBasicComponent,MiuixCard} from 'miuix-vue';
import appIcon from '../assets/opairdrop.svg';
defineProps<{version?:string}>();
defineEmits<{licenses:[]}>();
</script>
<template>
 <section class="about-screen" aria-label="关于 OPAirDrop PME110">
  <div class="about-identity">
   <img class="app-icon" :src="appIcon" width="120" height="120" alt="OPAirDrop 图标"/>
   <h1>OPAirDrop PME110</h1>
   <p>版本: {{version||'读取中'}}</p>
   <p>作者: <a href="https://github.com/weijuns" target="_blank" rel="noopener noreferrer">weijuns</a></p>
   <p class="thanks-label">感谢原作者</p>
   <p><a href="https://github.com/Weverses/OPAirDrop" target="_blank" rel="noopener noreferrer">TimelessU / Weverses · OPAirDrop</a></p>
   <p><a href="https://github.com/34306/AirDropVivoCN" target="_blank" rel="noopener noreferrer">34306 · AirDropVivoCN</a></p>
   <p><a href="https://github.com/fei-ke/unlock-cn-gms" target="_blank" rel="noopener noreferrer">fei-ke · Unlock CN GMS</a></p>
  </div>
  <MiuixCard class="about-actions">
   <a class="project-link" href="https://github.com/weijuns/OPAirDrop-PME110" target="_blank" rel="noopener noreferrer"><MiuixBasicComponent title="在 GitHub 查看源码"><template #end><span class="entry-arrow" aria-hidden="true">›</span></template></MiuixBasicComponent></a>
   <MiuixBasicComponent title="开放源代码许可" clickable @click="$emit('licenses')"><template #end><span class="entry-arrow" aria-hidden="true">›</span></template></MiuixBasicComponent>
  </MiuixCard>
 </section>
</template>
<style scoped>
.about-identity a{color:inherit;text-decoration:none}
.about-identity a:hover,.about-identity a:focus-visible{color:var(--m-color-primary);text-decoration:underline}
.about-identity .thanks-label{margin-top:18px;margin-bottom:4px;font-weight:550}
</style>
