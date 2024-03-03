import { defineMermaidSetup } from '@slidev/types'

export default defineMermaidSetup(() => {
  return {
    theme: 'forest',
    themeVariables: {
      lineColor: '#F8B229',
      fontFamily: "verdana",
      edgeLabelBackground: '#fff0',
    },
    sequence :{
      wrap: true,
      width:400,
      mirrorActors: false
    }
  }
})