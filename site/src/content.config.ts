import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const exampleSchema = z.object({
  text: z.string(),
  reading: z.string().optional().default(''),
  annot: z.string().optional().default(''),
  translation_zh: z.string().optional().default(''),
  source_book: z.string().optional().default(''),
  source_chapter: z.number().nullable().optional(),
});

const relatedSchema = z
  .object({
    cross_lang: z.array(z.string()).optional().default([]),
    same_lang: z
      .array(z.object({ id: z.string(), relation: z.string() }).passthrough())
      .optional()
      .default([]),
  })
  .optional()
  .default({ cross_lang: [], same_lang: [] });

const grammar = defineCollection({
  loader: glob({ pattern: '**/*.yaml', base: './src/content/kb/grammar' }),
  schema: z.object({
    id: z.string(),
    language: z.enum(['ja', 'ko', 'th', 'vi']),
    type: z.string().optional().default('grammar'),
    level: z.string(),
    level_rank: z.number(),
    title: z.string(),
    structure: z.string().optional().default(''),
    structure_pattern: z.string().optional().default(''),
    explanation_zh: z.string().optional().default(''),
    examples: z.array(exampleSchema).optional().default([]),
    related: relatedSchema,
    tags: z.array(z.string()).optional().default([]),
    provenance: z.any().optional(),
    status: z.string().optional().default('draft'),
    review_note: z.string().optional().default(''),
  }),
});

const vocab = defineCollection({
  loader: glob({ pattern: '**/*.yaml', base: './src/content/kb/vocab' }),
  schema: z.object({
    id: z.string(),
    language: z.enum(['ja', 'ko', 'th', 'vi']),
    word: z.string(),
    reading: z.string().optional().default(''),
    pos: z.string().optional().default(''),
    gloss_zh: z.string().optional().default(''),
    gloss_detail_zh: z.string().optional().default(''),
    level: z.string().optional().default(''),
    level_rank: z.number().optional().default(0),
    frequency: z.any().optional(),
    examples: z.array(exampleSchema).optional().default([]),
    related: relatedSchema,
    tags: z.array(z.string()).optional().default([]),
    provenance: z.any().optional(),
    status: z.string().optional().default('draft'),
  }),
});

const tutorials = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/kb/tutorials' }),
  schema: z.object({
    id: z.string(),
    level: z.string(),
    status: z.string(),
  }),
});

const links = defineCollection({
  loader: glob({ pattern: '**/*.yaml', base: './src/content/kb/links' }),
  schema: z.object({
    group_id: z.string(),
    concept_zh: z.string(),
    members: z.record(z.array(z.string())).optional().default({}),
    note_zh: z.string().optional().default(''),
    status: z.string().optional().default('draft'),
  }),
});

export const collections = { grammar, vocab, tutorials, links };
