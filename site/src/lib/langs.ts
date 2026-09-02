export const LANGS = ['ja', 'ko', 'th', 'vi'] as const;
export type Lang = (typeof LANGS)[number];

export const LANG_META: Record<
  Lang,
  { name: string; short: string; flag: string; accent: string; grad: string; levelLabel: (lv: string) => string }
> = {
  ja: {
    name: '日语', short: '日', flag: '🇯🇵',
    accent: '#f472b6', grad: 'from-rose-500/30 to-pink-500/10',
    levelLabel: (lv) => `JLPT ${lv}`,
  },
  ko: {
    name: '韩语', short: '韩', flag: '🇰🇷',
    accent: '#60a5fa', grad: 'from-sky-500/30 to-blue-500/10',
    levelLabel: (lv) => lv.replace('TOPIK', 'TOPIK '),
  },
  th: {
    name: '泰语', short: '泰', flag: '🇹🇭',
    accent: '#fbbf24', grad: 'from-amber-500/30 to-yellow-500/10',
    levelLabel: (lv) => `入门 ${lv}`,
  },
  vi: {
    name: '越南语', short: '越', flag: '🇻🇳',
    accent: '#34d399', grad: 'from-emerald-500/30 to-teal-500/10',
    levelLabel: (lv) => `入门 ${lv}`,
  },
};

export const POS_LABEL: Record<string, string> = {
  noun: '名词', verb: '动词', adj: '形容词', adv: '副词',
  func: '功能词', affix: '词缀', other: '其他',
};
