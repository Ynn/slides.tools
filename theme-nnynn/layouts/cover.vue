<script setup lang="ts">
import { computed } from 'vue'
import { handleBackground } from '../layoutHelper'

const props = defineProps({
  background: {
    // random image from a curated Unsplash collection by Anthony
    default: 'https://source.unsplash.com/collection/94734566/1920x1080',
  },
  author :{
    default: ''
  },
  mail :{
    default: ''
  }
})

const style = computed(() => handleBackground(props.background, true))
</script>

<template>
  <div
    class="slidev-layout cover text-center"
    :style="style"
  >
    <div class="my-auto w-full">
      <div class="content">
        <slot />
      </div>
      <div class="author">
        {{author}} <span  v-if="mail">- ({{ mail }})</span>
      </div>
      <div class="flex justify-center items-center p-4">
        <img class="text-center" width="50px" src="../assets/star.svg"/>
      </div>
    </div>
  </div>
</template>
