export function Icon({ name, size = 18 }: {name:string; size?:number}) {
  const icons: Record<string,string> = { home:"⌂", discover:"◈", movie:"▣", anime:"✦", tv:"▤", game:"◉", book:"▰", memory:"◌", data:"▧", ai:"✺", settings:"⚙", plus:"+", search:"⌕", sparkle:"✦", arrow:"→", close:"×", download:"↓", upload:"↑", trash:"⌫" };
  return <span aria-hidden style={{fontSize:size, lineHeight:1, display:"inline-flex"}}>{icons[name] || "·"}</span>;
}

