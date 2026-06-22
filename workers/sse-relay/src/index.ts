export default {
  async fetch(_req: Request): Promise<Response> {
    return new Response("SSE relay stub", { status: 200 });
  },
};
