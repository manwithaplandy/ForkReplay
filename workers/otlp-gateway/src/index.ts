export default {
  async fetch(_req: Request): Promise<Response> {
    return new Response("OTLP gateway stub", { status: 200 });
  },
};
