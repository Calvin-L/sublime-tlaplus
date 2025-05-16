\* SYNTAX TEST "tlaplus.sublime-syntax"

Hello!
\* <- comment

---- MODULE syntax_test_tla ----

Foo() == 1
\* <- entity.name.operator
         \* <- constant.numeric

Foo () == 1
\* <- entity.name.operator

Foo (* hehe comment *) == 1
\* <- entity.name.operator
       \* <- comment.block

Foo == bar()
        \* <- variable.function

Foo == bar((*comment*))
        \* <- variable.function
               \* <- comment.block

Foo == bar(*comment*)
        \* <- - variable.function

(* (* inner content *) *)
\*           ^^^ comment.block

Foo == "VEND" /\ pkt2.type = "VEND"
         \* <- string
                  \* <- - string
                               \* <- string

(*

Let's do some pluscal!
\* <- comment.block

--algorithm A {
\* <- - comment.block

    process (P \in 1 .. 2)
    \* ^^^^ keyword
    \* ^^^^ source.tlaplus
    {
        \* TODO: something?
        \* ^^^^ - comment.block
        \* ^^^^ comment.line
        "label":
          \* <- string
        while (TRUE) {
          \* <- keyword
            either {
              \* <- keyword
                (* do some checks *)
                \* ^^^^ comment.block
                if (Cardinality({s \in set : TRUE}) < 2) {
                      \* <- variable.function
                }
            }
        }
    }

}
\* <- - comment.block

All done!
\* <- comment.block

(*
open another comment scope "just in case"

--algorithm A2
         \* ^ - comment
    variable object = InitObj
      \* <- keyword

    process Proc \in Procs
        variables com, b;
        begin
            labelone: while TRUE do
                        with x \in SomeFunc(self) do
                            object := "a";
                        end with;

            labeltwo:       with result \in OtherFunc(self, com, object) do
                            object := b;
                        end with;
            end while;
    end process

end algorithm
\* <- keyword
      \* <- keyword
*)

*)

Foo == 10
\* <- - comment.block
\* <- entity.name.operator

    _UnderscoredID == FALSE
\*  ^^^^^^^^^^^^^^ <- entity.name.operator

====
